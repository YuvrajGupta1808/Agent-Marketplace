from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class SellerState(TypedDict, total=False):
    task_id: str
    query: str
    seller_agent_id: str
    retrieval_context: str
    research_output: str
    output: dict[str, Any]
