from __future__ import annotations

from seller_agent.state import SellerState
from shared.repository import repository
from shared.seller_config import seller_tool_ids


def load_seller_profile(state: SellerState) -> dict:
    seller = repository.get_agent(state["seller_agent_id"])
    if seller.role != "seller":
        raise ValueError("seller_agent_id must reference a seller agent.")

    return {
        "seller_name": seller.name,
        "seller_description": seller.description,
        "seller_system_prompt": seller.system_prompt,
        "seller_metadata": seller.metadata,
        "seller_tool_ids": seller_tool_ids(seller),
    }
