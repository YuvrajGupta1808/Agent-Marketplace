from __future__ import annotations

from buyer_agent.state import BuyerState
from shared.config import get_settings
from shared.repository import repository
from shared.seller_config import is_seller_published


def _score_seller(seller_record, query: str) -> int:
    """Score a seller's fitness for a given query. Higher is better."""
    if not isinstance(seller_record.metadata, dict):
        return 0

    query_lower = query.lower()
    query_tokens = set(query_lower.split())
    score = 0

    category = str(seller_record.metadata.get("category") or "").lower()
    if category and category in query_lower:
        score += 10

    use_case = str(seller_record.metadata.get("use_case") or seller_record.metadata.get("description") or "").lower()
    use_case_tokens = set(use_case.split())
    score += len(query_tokens & use_case_tokens)

    built_in_tools = seller_record.metadata.get("built_in_tools") or []
    for tool_id in built_in_tools:
        tool_keywords = set(tool_id.replace("_", " ").split())
        if query_tokens & tool_keywords:
            score += 3

    return score


def _select_best_seller(connected_ids: list[str], query: str) -> str:
    """Pick the seller from connected_ids that best matches the query.
    Falls back to connected_ids[0] if nothing loads or no score differs."""
    best_id = connected_ids[0]
    best_score = -1

    for seller_id in connected_ids:
        try:
            seller_record = repository.get_agent(seller_id)
        except (KeyError, Exception):
            continue
        score = _score_seller(seller_record, query)
        if score > best_score:
            best_score = score
            best_id = seller_id

    return best_id


def discover_seller(state: BuyerState) -> dict:
    settings = get_settings()

    connected_ids = state.get("buyer_agent_connected_seller_ids", [])
    requested_seller_id = state.get("seller_agent_id")

    if not connected_ids:
        raise ValueError("No seller agents connected to this buyer. Connect sellers before running.")

    if requested_seller_id and requested_seller_id in connected_ids:
        seller_id = requested_seller_id
    else:
        seller_id = _select_best_seller(connected_ids, state.get("query", ""))

    print(f"  🔍 discover_seller: seller_agent_id={seller_id}")
    seller = repository.get_agent(seller_id)
    if seller.role != "seller":
        raise ValueError(f"Agent {seller.id} is not a seller.")
    if not is_seller_published(seller):
        raise ValueError(f"Seller agent {seller.id} is not published.")
    seller_url = seller.endpoint_url or f"{settings.seller_base_url}{settings.seller_research_path}"
    print(f"    ✓ Seller endpoint: {seller_url}")
    return {
        "seller_agent_id": seller.id,
        "seller_url": seller_url,
        "seller_wallet_id": seller.wallet.circle_wallet_id,
        "seller_wallet_address": seller.wallet.address,
    }
