#!/usr/bin/env python3
"""Debug the research flow to find the 500 error."""
from __future__ import annotations

import os
import sys
import traceback

os.environ["CIRCLE_API_KEY"] = ""
os.environ["CIRCLE_ENTITY_SECRET"] = ""

from unittest.mock import patch
from fastapi.testclient import TestClient
from api.server import app as api_app
from seller_agent.server import app as seller_app


class SellerProxy:
    def __init__(self, *_: any, **__: any) -> None:
        self._inner = TestClient(seller_app)

    def __enter__(self) -> TestClient:
        self._inner.__enter__()
        return self._inner

    def __exit__(self, exc_type, exc, tb):
        return self._inner.__exit__(exc_type, exc, tb)

    def post(self, url: str, **kwargs):
        if "://" in url:
            path = url.split("://", 1)[1].split("/", 1)[1]
            path = "/" + path
        else:
            path = url
        print(f"  → POST {path}")
        response = self._inner.post(path, **kwargs)
        print(f"  ← Response: {response.status_code}")
        if response.status_code >= 400:
            try:
                print(f"     Error: {response.json()}")
            except:
                print(f"     Body: {response.text[:200]}")
        return response


def test():
    """Test the complete flow with debugging."""
    print("🔍 Testing Agent Marketplace Flow with Debug Output\n")

    with patch("httpx.Client", SellerProxy):
        client = TestClient(api_app, raise_server_exceptions=False)

        # Step 1: Create user
        print("Step 1: Creating user...")
        try:
            resp = client.post("/users", json={"display_name": "Debug User"})
            if resp.status_code >= 400:
                print(f"  ❌ Error: {resp.status_code} - {resp.text}")
                return
            user = resp.json()["user"]
            print(f"  ✓ User created: {user['id']}\n")
        except Exception as e:
            print(f"  ❌ Exception: {e}\n")
            return

        # Step 2: Create buyer
        print("Step 2: Creating buyer agent...")
        try:
            resp = client.post("/agents", json={
                "user_id": user["id"],
                "role": "buyer",
                "name": "Debug Buyer"
            })
            if resp.status_code >= 400:
                print(f"  ❌ Error: {resp.status_code} - {resp.text}")
                return
            buyer = resp.json()["agent"]
            print(f"  ✓ Buyer created: {buyer['id']}")
            print(f"  ✓ Wallet: {buyer['wallet']['address']}\n")
        except Exception as e:
            print(f"  ❌ Exception: {e}\n")
            return

        # Step 3: Create seller
        print("Step 3: Creating seller agent...")
        try:
            resp = client.post("/agents", json={
                "user_id": user["id"],
                "role": "seller",
                "name": "Debug Seller"
            })
            if resp.status_code >= 400:
                print(f"  ❌ Error: {resp.status_code} - {resp.text}")
                return
            seller = resp.json()["agent"]
            print(f"  ✓ Seller created: {seller['id']}")
            print(f"  ✓ Wallet: {seller['wallet']['address']}\n")
        except Exception as e:
            print(f"  ❌ Exception: {e}\n")
            return

        # Step 4: Run marketplace
        print("Step 4: Running marketplace research...")
        try:
            resp = client.post("/run", json={
                "user_goal": "What is Arc?",
                "thread_id": "debug-1",
                "buyer_agent_id": buyer["id"],
                "seller_agent_id": seller["id"]
            })
            print(f"\n  Response status: {resp.status_code}")
            if resp.status_code >= 400:
                print(f"  ❌ Error!")
                try:
                    error = resp.json()
                    print(f"     Detail: {error.get('detail', 'Unknown error')}")
                except:
                    print(f"     Body: {resp.text[:500]}")
                return

            result = resp.json()
            print(f"  ✓ Success!\n")

            # Display results
            print("📊 Results:")
            if result.get("final_answer"):
                print(f"\n  Final Answer (first 100 chars):")
                print(f"  {result['final_answer'][:100]}...")

            payments = result.get("payments", [])
            print(f"\n  Payments: {len(payments)}")
            for p in payments:
                print(f"    - Task {p['task_id']}: {p['amount_usdc']} USDC, State: {p['state']}")

            print(f"\n  ✅ All steps completed successfully!")

        except Exception as e:
            print(f"  ❌ Exception: {e}")
            traceback.print_exc()
            return


if __name__ == "__main__":
    test()
