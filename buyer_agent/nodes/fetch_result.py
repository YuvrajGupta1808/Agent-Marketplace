from __future__ import annotations

from buyer_agent.state import BuyerState
from shared.types import ResearchResult


def fetch_result(state: BuyerState) -> dict:
    if state.get("error"):
        return {"error": state["error"]}

    payload = state["response_body"]
    result = ResearchResult.model_validate(payload["result"])
    receipt = state.get("payment_receipt") or {}
    if receipt.get("tx_hash"):
        result.tx_hash = receipt["tx_hash"]
    if receipt.get("transaction_id"):
        result.circle_transaction_id = receipt["transaction_id"]
    if receipt.get("amount_usdc"):
        result.amount_usdc = receipt["amount_usdc"]
    return {"result": result.model_dump()}

