from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import streamlit as st
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load .env file before importing config
load_dotenv(Path(__file__).parent / ".env", override=True)

from api.server import app as api_app
from seller_agent.server import app as seller_app
from shared.config import get_settings

# Clear cached settings to ensure fresh load from .env
get_settings.cache_clear()

st.set_page_config(
    page_title="Agent Marketplace",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global API Client (reused across requests) ──────────────────────────────

@st.cache_resource
def get_api_client():
    """Create and cache a single API client for all requests."""
    with patch("httpx.Client", SellerProxy):
        return TestClient(api_app, raise_server_exceptions=False)

# ── Session State Initialization ──────────────────────────────────────────────

def init_session_state():
    st.session_state.setdefault("current_user", None)
    st.session_state.setdefault("current_buyer", None)
    st.session_state.setdefault("current_seller", None)
    st.session_state.setdefault("buyer_wallet_address", None)
    st.session_state.setdefault("buyer_wallet_funded", False)
    st.session_state.setdefault("research_results", None)
    st.session_state.setdefault("research_error", None)

init_session_state()

# ── Helpers ───────────────────────────────────────────────────────────────────

class SellerProxy:
    def __init__(self, *_: Any, **__: Any) -> None:
        self._inner = TestClient(seller_app)
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def post(self, url: str, **kwargs):
        """Intercept POST requests and redirect to seller TestClient."""
        if "://" in url:
            path = url.split("://", 1)[1].split("/", 1)[1]
            path = "/" + path
        else:
            path = url
        return self._inner.post(path, **kwargs)

    def post(self, url: str, **kwargs):
        if "://" in url:
            path = url.split("://", 1)[1].split("/", 1)[1]
            path = "/" + path
        else:
            path = url
        return self._inner.post(path, **kwargs)


def api_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make API request using cached embedded client."""
    client = get_api_client()
    response = client.request(method, path, json=payload)

    if response.status_code >= 400:
        try:
            body = response.json()
            detail = body.get("detail") or body.get("message") or response.text
        except Exception:
            detail = response.text
        raise RuntimeError(f"HTTP {response.status_code}: {detail}")

    return response.json()


# ── Main UI ───────────────────────────────────────────────────────────────────

st.title("🤖 Agent Marketplace")
st.markdown("Complete flow: User → Register → Fund Wallet → Plan Research → Payment → Results")

# Create tabs for the flow
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Register User",
    "2️⃣ Setup Agents",
    "3️⃣ Fund Wallet",
    "4️⃣ Plan & Pay",
    "5️⃣ Results"
])

# ── TAB 1: Register User ──────────────────────────────────────────────────────
with tab1:
    st.header("Register New User")

    col1, col2 = st.columns(2)
    with col1:
        user_display_name = st.text_input(
            "User Display Name",
            value="Demo User",
            key="user_display_name"
        )
    with col2:
        if st.button("✅ Register User", key="btn_register_user", use_container_width=True):
            try:
                with st.spinner("Registering user..."):
                    result = api_request("POST", "/users", {
                        "display_name": user_display_name
                    })
                    user = result["user"]
                    st.session_state.current_user = user
                    st.success(f"✅ User registered: {user['id']}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")

    if st.session_state.current_user:
        user = st.session_state.current_user
        st.info(f"""
        **Current User:**
        - ID: `{user['id']}`
        - Name: {user['display_name']}
        - Created: {user['created_at']}
        """)


# ── TAB 2: Setup Agents ───────────────────────────────────────────────────────
with tab2:
    st.header("Setup Buyer & Seller Agents")

    if not st.session_state.current_user:
        st.warning("⚠️ Please register a user in Tab 1 first")
    else:
        user_id = st.session_state.current_user["id"]

        col1, col2 = st.columns(2)

        # Buyer Agent
        with col1:
            st.subheader("👤 Buyer Agent")
            buyer_name = st.text_input("Buyer Name", value="Demo Buyer", key="buyer_name")

            if st.button("Create Buyer", key="btn_create_buyer", use_container_width=True):
                try:
                    with st.spinner("Creating buyer agent..."):
                        result = api_request("POST", "/agents", {
                            "user_id": user_id,
                            "role": "buyer",
                            "name": buyer_name
                        })
                        buyer = result["agent"]
                        st.session_state.current_buyer = buyer
                        st.session_state.buyer_wallet_address = buyer["wallet"]["address"]
                        st.success(f"✅ Buyer created")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")

            if st.session_state.current_buyer:
                buyer = st.session_state.current_buyer
                st.success(f"""
                **Buyer Agent Created**
                - ID: `{buyer['id']}`
                - Wallet: `{buyer['wallet']['address']}`
                """)

        # Seller Agent
        with col2:
            st.subheader("🔬 Research Agent (Seller)")
            seller_name = st.text_input("Research Agent Name", value="Demo Researcher", key="seller_name")

            if st.button("Create Seller", key="btn_create_seller", use_container_width=True):
                try:
                    with st.spinner("Creating research agent..."):
                        result = api_request("POST", "/agents", {
                            "user_id": user_id,
                            "role": "seller",
                            "name": seller_name
                        })
                        seller = result["agent"]
                        st.session_state.current_seller = seller
                        st.success(f"✅ Research agent created")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")

            if st.session_state.current_seller:
                seller = st.session_state.current_seller
                st.success(f"""
                **Research Agent Created**
                - ID: `{seller['id']}`
                - Wallet: `{seller['wallet']['address']}`
                """)


# ── TAB 3: Fund Wallet ────────────────────────────────────────────────────────
with tab3:
    st.header("💰 Fund Buyer Wallet")

    if not st.session_state.current_buyer:
        st.warning("⚠️ Create buyer agent in Tab 2 first")
    else:
        buyer = st.session_state.current_buyer
        wallet_addr = buyer["wallet"]["address"]

        settings = get_settings()

        st.info(f"""
        **Circle Wallet Details:**
        - Network: Arc Testnet (Chain 5042002)
        - Wallet Address: `{wallet_addr}`
        - Circle Wallet ID: `{buyer['wallet']['circle_wallet_id']}`
        - Account Type: {buyer['wallet']['account_type']}
        - Blockchain: {buyer['wallet']['blockchain']}
        """)

        if settings.circle_enabled:
            st.success("""
            ✅ **REAL CIRCLE MODE ACTIVE**

            This wallet is created on Circle Programmable Wallets.

            **To fund this wallet:**
            1. Open: https://faucet.circle.com
            2. Select Network: **Arc Testnet**
            3. Paste wallet address
            4. Request 10+ USDC
            5. Wait for confirmation

            **After funding:**
            - Your research queries will execute real payments
            - Transactions will be on Arc Testnet blockchain
            - Check explorer: https://testnet.arcscan.app
            """)
        else:
            st.success("""
            **Demo/Stub Mode (No Real Funding Needed):**

            You're using stub mode - wallets and payments are simulated.
            Click below to proceed without real funding.
            """)

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            amount_usdc = st.number_input(
                "Amount (USDC)",
                min_value=0.001,
                value=10.0,
                step=1.0
            )

        with col2:
            if settings.circle_enabled:
                if st.button("💳 Open Faucet", key="btn_open_faucet", use_container_width=True):
                    st.info("🔗 Open in browser: https://faucet.circle.com")
            else:
                if st.button("✅ Proceed (Stub)", key="btn_auto_fund", use_container_width=True):
                    st.session_state.buyer_wallet_funded = True
                    st.rerun()

        with col3:
            if st.button("⏭️ Skip & Continue", key="btn_skip_funding", use_container_width=True):
                st.session_state.buyer_wallet_funded = True
                st.rerun()

        if st.session_state.buyer_wallet_funded:
            if settings.circle_enabled:
                st.success(f"""
                ✅ **Circle Wallet Configured**
                - Address: `{wallet_addr}`
                - Status: Ready for funding via faucet
                - Network: Arc Testnet
                - Next: Fund via Circle faucet, then proceed to research
                """)
            else:
                st.success(f"""
                ✅ **Wallet Ready (Stub Mode)**
                - Address: `{wallet_addr}`
                - Balance: {amount_usdc} USDC (simulated)
                - Mode: Demo
                - Ready for research payments ✓
                """)


# ── TAB 4: Plan & Pay ─────────────────────────────────────────────────────────
with tab4:
    st.header("🔄 Plan Research & Execute Payment")

    if not st.session_state.current_buyer or not st.session_state.current_seller:
        st.warning("⚠️ Setup both agents in Tab 2 first")
    elif not st.session_state.buyer_wallet_funded:
        st.warning("⚠️ Fund wallet in Tab 3 first")
    else:
        user = st.session_state.current_user
        buyer = st.session_state.current_buyer
        seller = st.session_state.current_seller

        st.subheader("📝 Research Query")
        user_goal = st.text_area(
            "What would you like to research?",
            value="What is Arc Testnet and how does it work?",
            height=100,
            key="user_goal"
        )

        if st.button("🚀 Start Research Flow", key="btn_start_research", use_container_width=True):
            try:
                with st.spinner("🔄 Executing research flow..."):
                    st.info("Step 1: 📋 Planning research tasks...")

                    st.info("Step 2: 💳 Buyer initiating payment to research agent...")

                    st.info("Step 3: 🔬 Research agent executing query...")

                    st.info("Step 4: 📊 Synthesizing results...")

                    # Execute the marketplace flow
                    result = api_request("POST", "/run", {
                        "user_goal": user_goal,
                        "thread_id": f"demo-{uuid.uuid4().hex[:8]}",
                        "buyer_agent_id": buyer["id"],
                        "seller_agent_id": seller["id"]
                    })

                    st.session_state.research_results = result
                    st.session_state.research_error = None

                    st.success("✅ Research flow completed!")
                    st.rerun()

            except Exception as e:
                st.session_state.research_error = str(e)
                st.error(f"❌ Error: {e}")


# ── TAB 5: Results ────────────────────────────────────────────────────────────
with tab5:
    st.header("📊 Research Results")

    if not st.session_state.research_results:
        if st.session_state.research_error:
            st.error(f"❌ {st.session_state.research_error}")
        else:
            st.info("Run the research flow in Tab 4 to see results")
    else:
        result = st.session_state.research_results

        # Final Answer
        if result.get("final_answer"):
            st.subheader("✅ Final Answer")
            st.markdown(result["final_answer"])

        # Payments
        payments = result.get("payments", [])
        if payments:
            st.subheader(f"💳 Payments ({len(payments)})")
            for i, payment in enumerate(payments, 1):
                with st.expander(f"Payment {i}: {payment.get('task_id')}"):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Amount", f"{payment.get('amount_usdc')} USDC")
                    with col2:
                        st.metric("State", payment.get('state'))
                    with col3:
                        st.metric("Transaction", payment.get('circle_transaction_id', 'N/A')[:20])
                    with col4:
                        st.metric("TX Hash", payment.get('tx_hash', 'N/A')[:20])

        # Transaction Hashes
        tx_hashes = result.get("transaction_hashes", [])
        if tx_hashes:
            st.subheader(f"🔗 On-Chain Transactions ({len(tx_hashes)})")
            for tx_hash in tx_hashes:
                st.code(tx_hash)

        # Debug Info
        with st.expander("🔍 Debug Info"):
            st.json({
                "thread_id": result.get("thread_id"),
                "pending_question": result.get("pending_question"),
                "failed_tasks": result.get("failed_tasks", [])
            })


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("📋 Session Info")

if st.session_state.current_user:
    st.sidebar.success(f"👤 User: {st.session_state.current_user['display_name']}")
else:
    st.sidebar.info("No user registered yet")

if st.session_state.current_buyer:
    st.sidebar.success(f"👤 Buyer: {st.session_state.current_buyer['name']}")
else:
    st.sidebar.info("No buyer agent created yet")

if st.session_state.current_seller:
    st.sidebar.success(f"🔬 Seller: {st.session_state.current_seller['name']}")
else:
    st.sidebar.info("No research agent created yet")

st.sidebar.divider()

if st.sidebar.button("🔄 Reset All", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()
    st.rerun()

st.sidebar.info("""
**Flow:**
1. Register user
2. Create buyer & seller
3. Fund buyer wallet
4. Submit research query
5. View results & payments
""")
