from __future__ import annotations

from buyer_agent.state import BuyerState
from shared.config import get_settings
from shared.repository import repository


def discover_seller(state: BuyerState) -> dict:
    print(f"  🔍 discover_seller: seller_agent_id={state['seller_agent_id']}")
    settings = get_settings()
    seller = repository.get_agent(state["seller_agent_id"])
    if seller.role != "seller":
        raise ValueError(f"Agent {seller.id} is not a seller.")
    seller_url = seller.endpoint_url or f"{settings.seller_base_url}{settings.seller_research_path}"
    print(f"    ✓ Seller endpoint: {seller_url}")
    return {
        "seller_url": seller_url,
        "seller_wallet_id": seller.wallet.circle_wallet_id,
        "seller_wallet_address": seller.wallet.address,
    }
