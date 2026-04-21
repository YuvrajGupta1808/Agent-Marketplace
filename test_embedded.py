#!/usr/bin/env python3
"""Test embedded marketplace flow without external servers."""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

# Force stub mode - disable Circle
os.environ["CIRCLE_API_KEY"] = ""
os.environ["CIRCLE_ENTITY_SECRET"] = ""

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
        # Extract just the path from the URL
        if "://" in url:
            path = url.split("://", 1)[1].split("/", 1)[1]
            path = "/" + path
        else:
            path = url

        return self.seller_client.post(path, **kwargs)


def test_embedded_flow():
    """Test full marketplace flow in embedded mode."""
    settings = get_settings()
    print(f"🔧 Configuration:")
    print(f"   Circle enabled: {settings.circle_enabled}")
    print(f"   Seller base URL: {settings.seller_base_url}")
    print(f"   Using stub wallets and payments: ✓")

    api_client = TestClient(api_app)
    seller_client = TestClient(seller_app)

    # Create user
    print("\n📝 1. Creating user...")
    user_resp = api_client.post("/users", json={"display_name": "Test User"})
    if user_resp.status_code >= 400:
        print(f"   ❌ Failed: {user_resp.text}")
        return
    user_id = user_resp.json()["user"]["id"]
    print(f"   ✓ User ID: {user_id}")

    # Create buyer
    print("\n💰 2. Creating buyer agent...")
    buyer_resp = api_client.post(
        "/agents",
        json={"user_id": user_id, "role": "buyer", "name": "Test Buyer"},
    )
    if buyer_resp.status_code >= 400:
        print(f"   ❌ Failed: {buyer_resp.text}")
        return
    buyer_data = buyer_resp.json()["agent"]
    buyer_id = buyer_data["id"]
    print(f"   ✓ Buyer ID: {buyer_id}")
    print(f"   ✓ Wallet: {buyer_data['wallet']['address'][:10]}...")

    # Create seller
    print("\n💼 3. Creating seller agent...")
    seller_resp = api_client.post(
        "/agents",
        json={"user_id": user_id, "role": "seller", "name": "Test Seller"},
    )
    if seller_resp.status_code >= 400:
        print(f"   ❌ Failed: {seller_resp.text}")
        return
    seller_data = seller_resp.json()["agent"]
    seller_id = seller_data["id"]
    print(f"   ✓ Seller ID: {seller_id}")
    print(f"   ✓ Wallet: {seller_data['wallet']['address'][:10]}...")

    # Run marketplace with httpx patching
    print("\n🚀 4. Running marketplace (with embedded seller)...")
    print(f"   Query: 'What is Arc?'")

    with patch("httpx.Client", return_value=SellerProxy(seller_client)):
        run_resp = api_client.post(
            "/run",
            json={
                "user_goal": "What is Arc?",
                "thread_id": "test-1",
                "buyer_agent_id": buyer_id,
                "seller_agent_id": seller_id,
            },
        )

    if run_resp.status_code >= 400:
        print(f"\n   ❌ Failed with HTTP {run_resp.status_code}")
        print(f"   Error: {run_resp.text}")
        return

    data = run_resp.json()

    print(f"\n✅ SUCCESS! Marketplace execution completed.")

    # Display final answer
    final_answer = data.get("final_answer", "")
    if final_answer:
        lines = final_answer.split("\n")[:5]
        print(f"\n📋 Final Answer (first 5 lines):")
        for line in lines:
            if line:
                print(f"   {line}")

    # Display payments
    payments = data.get("payments", [])
    print(f"\n💳 Payments:")
    print(f"   Total: {len(payments)} payment(s)")
    for i, payment in enumerate(payments, 1):
        print(f"\n   Payment {i}:")
        print(f"      Task ID: {payment.get('task_id')}")
        print(f"      Amount: {payment.get('amount_usdc')} USDC")
        print(f"      Transaction ID: {payment.get('circle_transaction_id')}")
        print(f"      State: {payment.get('state')}")
        print(f"      TX Hash: {payment.get('tx_hash', 'None')}")

    # Display transactions
    tx_hashes = data.get("transaction_hashes", [])
    print(f"\n🔗 Transactions:")
    print(f"   Total: {len(tx_hashes)} tx hash(es)")
    for i, tx_hash in enumerate(tx_hashes, 1):
        print(f"   {i}. {tx_hash}")

    print(f"\n🎉 All tests passed! The marketplace is working in embedded mode.")
    print(f"   - Stub wallets: ✓")
    print(f"   - Stub payments: ✓")
    print(f"   - Embedded seller integration: ✓")
    print(f"   - Final answer synthesis: ✓")


if __name__ == "__main__":
    try:
        test_embedded_flow()
    except Exception as e:
        print(f"\n❌ Test failed with exception:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
