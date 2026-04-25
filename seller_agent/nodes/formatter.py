from __future__ import annotations

from seller_agent.state import SellerState
from shared.types import ResearchResult


def format_response(state: SellerState) -> dict:
    """Format research output as simple text response."""
    output = state.get("research_output", "No output generated")
    tool_outputs = state.get("tool_outputs", [])
    seller_name = state.get("seller_name") or "Seller Agent"
    citations = state.get("citations", [])

    result = ResearchResult(
        task_id=state.get("task_id", ""),
        title=f"{seller_name}: {state.get('query', 'Research')[:80]}",
        summary=output,
        bullets=[],
        citations=citations,
        seller_name=seller_name,
        is_ambiguous=False,
        metadata={
            "seller_agent_id": state.get("seller_agent_id", ""),
            "built_in_tools": state.get("seller_tool_ids", []),
            "tool_outputs": tool_outputs,
        },
    )

    return {
        "output": output,
        "result": result.model_dump(),
        "task_id": state.get("task_id", ""),
        "query": state.get("query", ""),
        "seller_agent_id": state.get("seller_agent_id", ""),
        "tool_outputs": tool_outputs,
    }
