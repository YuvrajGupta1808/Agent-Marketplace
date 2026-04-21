from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class SellerState(TypedDict, total=False):
    task_id: str
    query: str
    seller_agent_id: str
    retrieval_context: list[dict[str, str]]
    draft_summary: str
    bullets: list[str]
    result: dict[str, Any]
