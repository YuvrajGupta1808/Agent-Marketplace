from __future__ import annotations

from seller_agent.state import SellerState
from shared.config import get_settings
from shared.types import ResearchCitation, ResearchResult


def format_response(state: SellerState) -> dict:
    settings = get_settings()
    citations = [ResearchCitation.model_validate(item) for item in state["retrieval_context"]]
    result = ResearchResult(
        task_id=state["task_id"],
        title=f"Research result for {state['query']}",
        summary=state["draft_summary"],
        bullets=state["bullets"],
        citations=citations,
        seller_endpoint=f"{settings.seller_base_url}{settings.seller_research_path}",
        metadata={"mode": settings.research_mode},
    )
    return {"result": result.model_dump()}

