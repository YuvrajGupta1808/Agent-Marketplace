from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class BuyerState(TypedDict, total=False):
    # Input
    user_goal: str
    task_id: str
    query: str

    # Agent identity
    buyer_agent_name: str
    buyer_agent_description: str
    buyer_agent_system_prompt: str
    buyer_agent_connected_seller_ids: list[str]

    # Scope validation
    within_scope: bool
    scope_rejection_reason: str

    # Task decomposition
    tasks: list[dict]
    task_results: list[dict]

    # Synthesis
    final_answer: str

    # Existing fields
    query_intent: str
    retry_count: int
    thinking: str
    research_plan: list[dict]
    execution_plan: list[str]
    current_phase: str
    phase_start_ms: float
    event_callback: Any
    thread_id: str
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

    # Routing decision (for backwards compat with existing nodes)
    needs_external_research: bool
    direct_answer: str | None
