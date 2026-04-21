#!/usr/bin/env python3
"""Test marketplace with real Circle credentials."""
from __future__ import annotations

import os
import sys

# Set Circle credentials BEFORE any imports
os.environ["CIRCLE_API_KEY"] = "b1d1c00a181a96c6c4f7235cd8c05df1:484693d4a336a17578c672b63e749188"
os.environ["CIRCLE_ENTITY_SECRET"] = "69d4a72583bafe7f3012188de1a43644d7abd99a0d7eee61d803131ba4fe06ce"

from unittest.mock import patch
from fastapi.testclient import TestClient
from api.server import app as api_app
from seller_agent.server import app as seller_app
from shared.config import get_settings


class SellerProxy:
    """Proxy that redirects HTTP calls to the seller TestClient."""

    def __init__(self, seller_client: TestClient):
        self.seller_client = seller_client
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def post(self, url: str, **kwargs):
        """Intercept POST requests and redirect to seller TestClient."""
        if "://" in url:
            path = url.split("://", 1)[1].split("/", 1)[1]
            path = "/" + path
        else:
            path = url
        return self.seller_client.post(path, **kwargs)


def test_with_circle():
    """Test marketplace with real Circle credentials."""
    settings = get_settings()
    print(f"🔧 Configuration:")
    print(f"   Circle enabled: {settings.circle_enabled}")
    print(f"   Circle API Key: {'***' + settings.circle_api_key.get_secret_value()[-8:] if settings.circle_api_key else 'None'}")

    if not settings.circle_enabled:
        print(f"\n❌ Circle credentials not loaded!")
        print(f"   Check that CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET are set")
        return

    print(f"\n✅ Circle is enabled! Testing with real Circle API...\n")

    api_client = TestClient(api_app)
    seller_client = TestClient(seller_app)

    # Create user
    print("📝 Creating user...")
    user_resp = api_client.post("/users", json={"display_name": "Circle Test User"})
    if user_resp.status_code >= 400:
        print(f"   ❌ Failed: {user_resp.text}")
        return
    user_id = user_resp.json()["user"]["id"]
    print(f"   ✓ User ID: {user_id}")

    # Create buyer
    print("\n💰 Creating buyer agent (with real Circle wallet)...")
    buyer_resp = api_client.post(
        "/agents",
        json={"user_id": user_id, "role": "buyer", "name": "Circle Buyer"},
    )
    if buyer_resp.status_code >= 400:
        print(f"   ❌ Failed: {buyer_resp.status_code}")
        print(f"   Error: {buyer_resp.text}")
        return
    buyer_data = buyer_resp.json()["agent"]
    buyer_id = buyer_data["id"]
    print(f"   ✓ Buyer ID: {buyer_id}")
    print(f"   ✓ Real Circle Wallet ID: {buyer_data['wallet']['circle_wallet_id']}")
    print(f"   ✓ Address: {buyer_data['wallet']['address']}")

    # Create seller
    print("\n💼 Creating seller agent (with real Circle wallet)...")
    seller_resp = api_client.post(
        "/agents",
        json={"user_id": user_id, "role": "seller", "name": "Circle Seller"},
    )
    if seller_resp.status_code >= 400:
        print(f"   ❌ Failed: {seller_resp.status_code}")
        print(f"   Error: {seller_resp.text}")
        return
    seller_data = seller_resp.json()["agent"]
    seller_id = seller_data["id"]
    print(f"   ✓ Seller ID: {seller_id}")
    print(f"   ✓ Real Circle Wallet ID: {seller_data['wallet']['circle_wallet_id']}")
    print(f"   ✓ Address: {seller_data['wallet']['address']}")

    # Run marketplace
    print("\n🚀 Running marketplace with real Circle wallets...")
    with patch("httpx.Client", return_value=SellerProxy(seller_client)):
        run_resp = api_client.post(
            "/run",
            json={
                "user_goal": "What is Arc?",
                "thread_id": "circle-test-1",
                "buyer_agent_id": buyer_id,
                "seller_agent_id": seller_id,
            },
        )

    if run_resp.status_code >= 400:
        print(f"\n   ❌ Failed with HTTP {run_resp.status_code}")
        print(f"   Error: {run_resp.text}")
        return

    data = run_resp.json()
    print(f"\n✅ SUCCESS! Marketplace executed with real Circle wallets.")

    # Display payments with real Circle data
    payments = data.get("payments", [])
    print(f"\n💳 Real Circle Payments:")
    print(f"   Total: {len(payments)} payment(s)")
    for i, payment in enumerate(payments, 1):
        print(f"\n   Payment {i}:")
        print(f"      Amount: {payment.get('amount_usdc')} USDC")
        print(f"      Circle Transaction ID: {payment.get('circle_transaction_id')}")
        print(f"      State: {payment.get('state')}")
        tx_hash = payment.get('tx_hash')
        if tx_hash and not tx_hash.startswith('0x0000'):
            print(f"      ✓ Real TX Hash: {tx_hash[:20]}...")
        else:
            print(f"      TX Hash: {tx_hash} (pending on-chain confirmation)")

    print(f"\n🎉 Real Circle integration working!")


if __name__ == "__main__":
    try:
        test_with_circle()
    except Exception as e:
        print(f"\n❌ Test failed:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
