from __future__ import annotations

from seller_agent.state import SellerState


def format_response(state: SellerState) -> dict:
    """Format research output as simple text response."""
    output = state.get("research_output", "No output generated")

    return {
        "output": output,
        "task_id": state.get("task_id", ""),
        "query": state.get("query", ""),
    }

