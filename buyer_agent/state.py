from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class BuyerState(TypedDict, total=False):
    task_id: str
    query: str
    query_intent: str
    retry_count: int
    reasoning: str
    research_plan: list[dict]
    execution_plan: list[str]
    current_phase: str
    phase_start_ms: float
    event_callback: Any
    buyer_agent_id: str
    buyer_wallet_id: str
    buyer_wallet_address: str
    seller_agent_id: str
    seller_url: str
    seller_wallet_id: str
    seller_wallet_address: str | None
    payment_authorization: dict[str, Any]
    payment_offer: dict[str, Any]
    payment_receipt: dict[str, Any]
    response_body: dict[str, Any]
    result: dict[str, Any]
    error: str
