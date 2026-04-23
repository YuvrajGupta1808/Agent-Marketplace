from __future__ import annotations

import json

import httpx

from buyer_agent.state import BuyerState
from shared.config import get_settings
from shared.x402_client import PAYMENT_RESPONSE_HEADER, PAYMENT_SIGNATURE_HEADER, PAYMENT_TX_ID_HEADER, PaymentReceipt


def send_research_request(state: BuyerState) -> dict:
    if state.get("error"):
        return {"error": state["error"]}

    settings = get_settings()
    authorization = state.get("payment_authorization") or {}
    receipt = state.get("payment_receipt") or {}

    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        paid = client.post(
            state["seller_url"],
            headers={
                PAYMENT_SIGNATURE_HEADER: json.dumps(authorization),
                PAYMENT_TX_ID_HEADER: receipt.get("transaction_id", ""),
            },
            json={
                "task_id": state["task_id"],
                "query": state["query"],
                "buyer_agent_id": state["buyer_agent_id"],
                "seller_agent_id": state["seller_agent_id"],
            },
        )

    if paid.status_code >= 400:
        return {"error": f"Research request failed with {paid.status_code}: {paid.text}"}

    if PAYMENT_RESPONSE_HEADER not in paid.headers:
        return {"error": "Seller response missing payment receipt header."}

    seller_receipt = PaymentReceipt.model_validate_json(paid.headers[PAYMENT_RESPONSE_HEADER])
    return {
        "payment_receipt": seller_receipt.model_dump(),
        "response_body": paid.json(),
    }
