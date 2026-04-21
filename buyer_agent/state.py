from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class BuyerState(TypedDict, total=False):
    task_id: str
    query: str
    retry_count: int
    buyer_agent_id: str
    buyer_wallet_id: str
    buyer_wallet_address: str
    seller_agent_id: str
    seller_url: str
    seller_wallet_id: str
    seller_wallet_address: str | None
    payment_offer: dict[str, Any]
    payment_receipt: dict[str, Any]
    response_body: dict[str, Any]
    result: dict[str, Any]
    error: str
