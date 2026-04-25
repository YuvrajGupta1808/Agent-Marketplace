from __future__ import annotations

from buyer_agent.state import BuyerState
from shared.config import get_settings
from shared.repository import repository
from shared.seller_config import is_seller_published


def discover_seller(state: BuyerState) -> dict:
    settings = get_settings()

    # 1. Try connected sellers first
    connected_ids = state.get("buyer_agent_connected_seller_ids", [])
    requested_seller_id = state.get("seller_agent_id")
    seller_id = requested_seller_id if requested_seller_id in connected_ids else None

    if not seller_id and connected_ids:
        # Use first connected seller (simple routing for now)
        seller_id = connected_ids[0]
    elif not seller_id:
        # Fallback to legacy pre-specified seller_agent_id for backwards compatibility
        seller_id = requested_seller_id

    if not seller_id:
        raise ValueError("No seller agent available. Connect a seller agent to this buyer.")

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
