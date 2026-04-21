from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from langgraph.types import Command

try:
    from circle.web3.configurations.exceptions import ApiException as CircleConfigApiException
    from circle.web3.developer_controlled_wallets.exceptions import (
        ApiException as CircleWalletApiException,
    )
    from circle.web3.developer_controlled_wallets.exceptions import BadRequestException as CircleWalletBadRequestException
except ImportError:
    # Circle SDK not installed - use fallback
    CircleConfigApiException = Exception  # type: ignore
    CircleWalletApiException = Exception  # type: ignore
    CircleWalletBadRequestException = Exception  # type: ignore

from orchestrator.graph import orchestrator_graph
from shared.circle_client import get_circle_client
from shared.config import get_settings
from shared.provisioning import ensure_circle_wallet_set_id
from shared.repository import repository
from shared.types import (
    CreateAgentRequest,
    CreateAgentResponse,
    CreateUserRequest,
    CreateUserResponse,
    PaymentRecord,
    ResumeRequest,
    RunRequest,
    RunResponse,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    repository  # initialize DB on startup
    yield


app = FastAPI(title="Agent Marketplace API", version="0.1.0", lifespan=lifespan)


@app.post("/users", response_model=CreateUserResponse)
def create_user(request: CreateUserRequest) -> CreateUserResponse:
    user = repository.create_user(request)
    return CreateUserResponse(user=user)


@app.post("/agents", response_model=CreateAgentResponse)
def create_agent(request: CreateAgentRequest) -> CreateAgentResponse:
    import uuid
    from shared.circle_client import CircleProvisionedWallet

    try:
        repository.get_user(request.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    settings = get_settings()
    endpoint_url = request.endpoint_url
    if request.role == "seller" and not endpoint_url:
        endpoint_url = f"{settings.seller_base_url}{settings.seller_research_path}"

    # Use real Circle wallets
    if not settings.circle_enabled:
        raise HTTPException(status_code=400, detail="Circle credentials not configured. Set CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET in .env")

    try:
        wallet_set_id = ensure_circle_wallet_set_id()
        wallet = get_circle_client().create_agent_wallet(
            wallet_set_id=wallet_set_id,
            ref_id=f"{request.role}:{request.user_id}",
            name=request.name,
        )
    except (CircleWalletBadRequestException, CircleWalletApiException, CircleConfigApiException) as exc:
        raise HTTPException(status_code=400, detail=f"Circle wallet creation failed: {exc}") from exc
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Wallet provisioning failed: {type(exc).__name__}: {str(exc)}") from exc

    agent = repository.create_agent(request.model_copy(update={"endpoint_url": endpoint_url}), wallet)
    return CreateAgentResponse(agent=agent)


def _poll_payment_status(circle_tx_id: str, max_retries: int = 3, retry_delay: float = 0.5) -> tuple[str | None, str]:
    import time
    state = "INITIATED"
    tx_hash = None
    for attempt in range(max_retries):
        try:
            tx = get_circle_client().get_transaction(circle_tx_id)
            state = tx.get("state", "INITIATED")
            tx_hash = tx.get("txHash") or tx.get("tx_hash")
            if state in ("CONFIRMED", "FAILED", "DENIED"):
                break
        except Exception:
            pass
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    return tx_hash, state


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "circle_enabled": get_settings().circle_enabled}


@app.post("/run", response_model=RunResponse)
def run_marketplace(request: RunRequest) -> RunResponse:
    # Validate agents exist
    try:
        buyer = repository.get_agent(request.buyer_agent_id)
        seller = repository.get_agent(request.seller_agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc

    if buyer.role != "buyer":
        raise HTTPException(status_code=400, detail="buyer_agent_id must reference a buyer agent.")
    if seller.role != "seller":
        raise HTTPException(status_code=400, detail="seller_agent_id must reference a seller agent.")

    try:
        result = orchestrator_graph.invoke(
            {
                "user_goal": request.user_goal,
                "thread_id": request.thread_id,
                "buyer_agent_id": request.buyer_agent_id,
                "seller_agent_id": request.seller_agent_id,
            },
            config={"configurable": {"thread_id": request.thread_id}},
        )
    except (CircleWalletBadRequestException, CircleWalletApiException, CircleConfigApiException) as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Marketplace run failed: {exc}") from exc
    except Exception as exc:
        import traceback
        error_msg = traceback.format_exc()
        print(f"\n❌ ERROR in orchestrator:\n{error_msg}\n")
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {str(exc)}") from exc

    # Poll Circle for payment confirmations if Circle is enabled
    payments = result.get("payments", [])
    tx_hashes = result.get("transaction_hashes", [])
    settings = get_settings()

    # Convert PaymentRecord objects to dicts if needed, then poll for updates
    if payments and settings.circle_enabled:
        payment_dicts = []
        for pmt in payments:
            # Convert Pydantic model to dict if needed
            pmt_dict = pmt.model_dump() if hasattr(pmt, 'model_dump') else dict(pmt)

            # Poll for transaction status
            if pmt_dict.get("circle_transaction_id") and not pmt_dict.get("tx_hash"):
                tx_hash, state = _poll_payment_status(pmt_dict["circle_transaction_id"])
                if tx_hash:
                    pmt_dict["tx_hash"] = tx_hash
                    if tx_hash not in tx_hashes:
                        tx_hashes.append(tx_hash)
                pmt_dict["state"] = state

            payment_dicts.append(pmt_dict)
        payments = payment_dicts

    return RunResponse(
        thread_id=request.thread_id,
        final_answer=result.get("final_answer"),
        running_answer=result.get("running_answer"),
        transaction_hashes=tx_hashes,
        payments=payments,
        failed_tasks=result.get("failed_tasks", []),
        pending_question=result.get("pending_question"),
    )


@app.post("/resume", response_model=RunResponse)
def resume_marketplace(request: ResumeRequest) -> RunResponse:
    result = orchestrator_graph.invoke(
        Command(resume=request.answer),
        config={"configurable": {"thread_id": request.thread_id}},
    )
    return RunResponse(
        thread_id=request.thread_id,
        final_answer=result.get("final_answer"),
        running_answer=result.get("running_answer"),
        transaction_hashes=result.get("transaction_hashes", []),
        payments=result.get("payments", []),
        failed_tasks=result.get("failed_tasks", []),
        pending_question=result.get("pending_question"),
    )


@app.get("/payments/{circle_transaction_id}")
def check_payment(circle_transaction_id: str) -> dict:
    if not get_settings().circle_enabled:
        return {
            "transaction_id": circle_transaction_id,
            "state": "STUB_MODE",
            "tx_hash": None,
            "amounts": [],
            "destination": None,
            "blockchain": None,
            "raw": {},
        }
    try:
        tx = get_circle_client().get_transaction(circle_transaction_id)
        return {
            "transaction_id": circle_transaction_id,
            "state": tx.get("state", "UNKNOWN"),
            "tx_hash": tx.get("txHash") or tx.get("tx_hash"),
            "amounts": tx.get("amounts", []),
            "destination": tx.get("destinationAddress") or tx.get("destination_address"),
            "blockchain": tx.get("blockchain"),
            "raw": tx,
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
