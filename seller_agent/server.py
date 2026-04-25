from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import AsyncIterator

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from seller_agent.graph import seller_graph
from shared.config import get_settings
from shared.circle_client import get_circle_client
from shared.provisioning import ensure_circle_wallet_set_id
from shared.repository import repository
from shared.seller_config import is_seller_published, seller_price_usdc
from shared.ssl import configure_ssl_cert_file
from shared.types import AgentRecord, ResearchRequest
from shared.x402_client import (
    PAYMENT_REQUIRED_HEADER,
    PAYMENT_RESPONSE_HEADER,
    PAYMENT_SIGNATURE_HEADER,
    PAYMENT_TX_ID_HEADER,
    PaymentOffer,
    PaymentReceipt,
    get_x402_client,
)

configure_ssl_cert_file()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    repository  # initialize DB on startup
    yield


app = FastAPI(title="Seller Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TestResearchRequest(BaseModel):
    query: str
    seller_agent_id: str
    user_id: str
    task_id: str = "test-task"


@app.post("/research")
def research_endpoint(
    request: ResearchRequest,
    payment_signature: str | None = Header(default=None, alias=PAYMENT_SIGNATURE_HEADER),
    payment_tx_id: str | None = Header(default=None, alias=PAYMENT_TX_ID_HEADER),
):
    seller: AgentRecord = repository.get_agent(request.seller_agent_id)
    if seller.role != "seller":
        raise HTTPException(status_code=400, detail="seller_agent_id must reference a seller agent.")
    if not is_seller_published(seller):
        raise HTTPException(status_code=403, detail="Seller agent is not published.")

    offer = get_x402_client().create_offer(
        seller.wallet.address,
        seller.id,
        amount_usdc=seller_price_usdc(seller),
    )

    if not payment_signature:
        return JSONResponse(
            status_code=402,
            content={"detail": "Payment required."},
            headers={PAYMENT_REQUIRED_HEADER: offer.model_dump_json()},
        )

    try:
        authorization = get_x402_client().verify_authorization(payment_signature, offer, request.query)
    except ValueError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    if authorization.buyer_agent_id != request.buyer_agent_id:
        raise HTTPException(status_code=402, detail="Buyer agent does not match payment authorization.")
    if not payment_tx_id:
        raise HTTPException(status_code=402, detail="Missing Circle transaction id.")
    if not get_settings().circle_enabled:
        raise HTTPException(status_code=400, detail="Circle credentials are required for seller payments.")

    transaction = get_circle_client().get_transaction(payment_tx_id)

    destination = (transaction.get("destination_address") or transaction.get("destinationAddress") or "").lower()
    amounts = transaction.get("amounts") or []
    if destination and destination != seller.wallet.address.lower():
        raise HTTPException(status_code=402, detail="Circle transaction destination does not match seller wallet.")
    if amounts and Decimal(str(amounts[0])) != Decimal(offer.amount_usdc):
        raise HTTPException(status_code=402, detail="Circle transaction amount does not match payment offer.")

    receipt = PaymentReceipt(
        transaction_id=payment_tx_id,
        transaction_state=transaction.get("state", "UNKNOWN"),
        tx_hash=transaction.get("tx_hash") or transaction.get("txHash"),
        amount_usdc=offer.amount_usdc,
        pay_to=seller.wallet.address,
    )

    graph_result = seller_graph.invoke(
        {
            "task_id": request.task_id,
            "query": request.query,
            "seller_agent_id": request.seller_agent_id,
        }
    )
    return JSONResponse(
        content=graph_result,
        headers={PAYMENT_RESPONSE_HEADER: receipt.model_dump_json()},
    )


@app.post("/research/test")
def research_test_endpoint(request: TestResearchRequest):
    """Direct research endpoint — no payment required. For development/testing only."""
    try:
        seller: AgentRecord = repository.get_agent(request.seller_agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Seller agent {request.seller_agent_id!r} not found.")
    if seller.role != "seller":
        raise HTTPException(status_code=400, detail="seller_agent_id must reference a seller agent.")
    if seller.user_id != request.user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to test this seller agent.")

    graph_result = seller_graph.invoke(
        {
            "task_id": request.task_id,
            "query": request.query,
            "seller_agent_id": request.seller_agent_id,
        }
    )
    return JSONResponse(content=graph_result)
