#!/usr/bin/env python3
"""
Idempotent database seeding script.
Creates demo seller and buyer agents on first run.
Checks app_config table for "seeded_v1" marker to skip if already run.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.repository import MarketplaceRepository
from shared.circle_client import get_circle_client
from shared.config import get_settings
from shared.provisioning import ensure_circle_wallet_set_id
from shared.types import CreateAgentRequest, CreateUserRequest


def seed_database() -> None:
    """Create demo agents if not already seeded."""
    settings = get_settings()
    repo = MarketplaceRepository()

    # Check if already seeded
    seeded = repo.get_app_config("seeded_v3")
    if seeded:
        print("✓ Database already seeded. Skipping.")
        return

    print("🌱 Seeding database...")

    # Check if Circle is enabled
    if not settings.circle_enabled:
        print("⚠️  Circle credentials not configured. Skipping agent seeding.")
        print("   → Set CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET to enable wallet creation")
        print("   → Agents can be created manually via the UI")
        repo.set_app_config("seeded_v3", "stub")
        return

    try:
        # Create test seller user with fake name
        seller_user_req = CreateUserRequest(display_name="Aurora Labs", external_id="aurora-labs")
        seller_user = repo.create_user(seller_user_req)
        print(f"  Created seller user: {seller_user.id}")

        # Provision Circle wallet for seller
        wallet_set_id = ensure_circle_wallet_set_id()
        circle_client = get_circle_client()
        wallet_info = circle_client.create_agent_wallet(
            wallet_set_id=wallet_set_id,
            ref_id=f"seller:{seller_user.id}",
            name="DuckDuckGo Search Agent",
        )
        wallet_address = wallet_info.address if hasattr(wallet_info, 'address') else wallet_info.get('address')
        print(f"  Created seller wallet: {wallet_address}")
        print(f"  ⚠️  Fund this wallet from Arc Testnet faucet: {wallet_address}")

        # Create seller agent
        seller_agent_req = CreateAgentRequest(
            user_id=seller_user.id,
            name="DuckDuckGo",
            role="seller",
            metadata={
                "description": "Privacy-focused search agent powered by DuckDuckGo API for instant information retrieval",
                "use_case": "Quick searches, privacy-preserving research, instant information lookup, anonymous browsing",
                "category": "Search",
                "creator_name": "Aurora Labs",
            },
        )
        seller_agent = repo.create_agent(seller_agent_req, wallet_info)
        print(f"  Created seller agent: {seller_agent.id}")

        # Mark as seeded
        repo.set_app_config("seeded_v3", "true")
        print("✓ Seeding complete!")

    except Exception as e:
        print(f"✗ Seeding failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    seed_database()
