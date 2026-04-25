from __future__ import annotations

from buyer_agent.state import BuyerState
from shared.types import ResearchResult


def format_direct_answer(state: BuyerState) -> dict:
    """Format a direct answer as a ResearchResult."""
    direct_answer = state.get("direct_answer", "")
    query = state.get("query", "Query")
    agent_name = state.get("buyer_agent_name") or "Buyer Agent"

    print(f"  📦 format_direct_answer: '{query[:50]}'")

    # Parse answer into title and summary
    lines = direct_answer.strip().split("\n")
    title = lines[0][:200] if lines else f"Answer: {query[:60]}"
    summary = "\n".join(lines[1:])[:2000] if len(lines) > 1 else direct_answer[:2000]

    structured_result = ResearchResult(
        task_id=state.get("task_id", ""),
        title=title,
        summary=summary,
        bullets=[],
        citations=[],
        seller_name=agent_name,
        is_ambiguous=False,
        metadata={},
    )

    print(f"    ✓ Formatted direct answer: {structured_result.title[:40]}")
    return {"result": structured_result.model_dump()}
