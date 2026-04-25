from __future__ import annotations

from seller_agent.state import SellerState
from shared.builtin_tools import run_builtin_tools


def retrieve_context(state: SellerState) -> dict:
    query = state["query"]
    tool_ids = state.get("seller_tool_ids", [])

    if not tool_ids:
        return {
            "retrieval_context": "",
            "tool_outputs": [],
            "citations": [],
        }

    result = run_builtin_tools(tool_ids, query)
    return {
        "retrieval_context": result.context,
        "tool_outputs": result.tool_outputs,
        "citations": result.citations,
    }
