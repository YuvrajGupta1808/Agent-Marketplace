from __future__ import annotations

from seller_agent.state import SellerState


def format_response(state: SellerState) -> dict:
    """Return raw seller output without imposing a fixed result schema."""
    output = state.get("research_output", "No output generated")
    tool_outputs = state.get("tool_outputs", [])

    return {
        "output": output,
        "task_id": state.get("task_id", ""),
        "query": state.get("query", ""),
        "seller_agent_id": state.get("seller_agent_id", ""),
        "seller_name": state.get("seller_name") or "Seller Agent",
        "built_in_tools": state.get("seller_tool_ids", []),
        "tool_outputs": tool_outputs,
    }
