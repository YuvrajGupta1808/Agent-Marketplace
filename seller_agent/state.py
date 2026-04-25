from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class SellerState(TypedDict, total=False):
    task_id: str
    query: str
    seller_agent_id: str
    seller_name: str
    seller_description: str
    seller_system_prompt: str
    seller_metadata: dict[str, Any]
    seller_tool_ids: list[str]
    retrieval_context: str
    tool_outputs: list[dict[str, Any]]
    citations: list[dict[str, str]]
    research_output: str
    output: dict[str, Any]
