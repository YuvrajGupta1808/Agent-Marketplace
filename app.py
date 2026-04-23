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
from shared.ssl import configure_ssl_cert_file

# Clear cached settings to ensure fresh load from .env
get_settings.cache_clear()
configure_ssl_cert_file()

st.set_page_config(
    page_title="Agent Marketplace",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Apply httpx.Client patch globally for entire session ──────────────────────

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


# Start the patch at module level so it's active for the entire session
_patcher = patch("httpx.Client", SellerProxy)
_patcher.start()

# ── Global API Client (reused across requests) ──────────────────────────────

@st.cache_resource
def get_api_client():
    """Create and cache a single API client for all requests."""
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


BUYER_WORKFLOW_STEPS = [
    ("discover_seller", "Discover Seller", "Resolve the seller endpoint and wallet."),
    ("plan_research", "Plan Buyer Steps", "Prepare the buyer-side execution plan."),
    ("execute_payment", "Execute Payment", "Authorize and settle the payment."),
    ("send_research", "Send Research", "Send the paid request to the seller."),
    ("fetch_result", "Fetch Result", "Normalize the final research result."),
]


def render_buyer_workflow_panel(result: dict[str, Any] | None = None) -> None:
    """Render the buyer agent workflow reflected in the LangGraph graph."""
    if not result:
        st.info("Run the workflow to see the buyer graph values.")
        return

    payments = result.get("payments", [])
    results = result.get("results", [])
    workflows = result.get("buyer_workflows", [])

    with st.expander("🤖 Buyer Agent Workflow", expanded=True):
        if workflows:
            for workflow in workflows:
                task_id = workflow.get("task_id", "task")
                st.write(f"**Task:** `{task_id}`")
                node_outputs = workflow.get("node_outputs", [])
                if node_outputs:
                    for index, node_output in enumerate(node_outputs, 1):
                        title = node_output.get("title", f"Step {index}")
                        input_state = node_output.get("input_state", {})
                        payload = node_output.get("output", {})
                        state_after = node_output.get("state_after", {})
                        has_output = any(value not in (None, "", [], {}) for value in payload.values())
                        status = "✅" if has_output else "⏳"

                        with st.expander(f"{status} {index}. {title}", expanded=True):
                            st.write("**Input State**")
                            if input_state:
                                st.json(input_state)
                            else:
                                st.caption("No input state captured.")

                            st.write("**Output**")
                            if payload:
                                st.json(payload)
                            else:
                                st.caption("No output captured for this node.")

                            st.write("**State After**")
                            if state_after:
                                st.json(state_after)
                            else:
                                st.caption("No post-node state captured.")
                    st.divider()
                    continue

                steps = workflow.get("execution_plan", [])
                if not steps:
                    st.info("No buyer execution steps were returned for this task.")
                    continue

                completed_count = 2
                if payments:
                    completed_count = 3
                if results:
                    completed_count = 5

                for index, step in enumerate(steps, 1):
                    status = "✅" if index <= completed_count else "⏳"
                    st.write(f"{status} {step}")
                st.divider()
            return

        completed_steps = set()
        if result:
            completed_steps.update({"discover_seller", "plan_research"})
        if payments:
            completed_steps.add("execute_payment")
        if results:
            completed_steps.update({"send_research", "fetch_result"})

        for step_id, title, description in BUYER_WORKFLOW_STEPS:
            status = "✅" if step_id in completed_steps else "⏳"
            st.write(f"{status} **{title}**")
            st.caption(description)


def render_plan_panel(goal: str, result: dict[str, Any]) -> None:
    """Render the planned tasks returned by the marketplace flow."""
    task_specs = result.get("task_specs", [])
    results = result.get("results", [])
    payments = result.get("payments", [])

    with st.expander("📋 Orchestrator Task Plan", expanded=True):
        st.write(f"**Goal:** {goal}")
        if task_specs:
            st.write("**Tasks Created:**")
            for i, spec in enumerate(task_specs, 1):
                query = spec.get("query", "Research task")
                st.write(f"{i}. Task `{spec.get('task_id', f'task-{i}')}`: {query}")
        elif results:
            st.write("**Completed Tasks:**")
            for i, res in enumerate(results, 1):
                st.write(f"{i}. Task `{res.get('task_id', f'task-{i}')}`: {res.get('title', 'Research task')}")
        elif payments:
            st.write("**Executed Tasks:**")
            for i, payment in enumerate(payments, 1):
                st.write(f"{i}. Task `{payment.get('task_id', f'task-{i}')}`: {goal}")
        else:
            st.info("No plan items were returned for this run.")


def render_payment_panel(result: dict[str, Any]) -> None:
    """Render payment records and explorer links for the current run."""
    payments = result.get("payments", [])

    with st.expander("💳 Payments & Transactions", expanded=True):
        if not payments:
            st.info("No payment records were returned for this run.")
            return

        for i, payment in enumerate(payments, 1):
            st.write(f"**Payment {i}:** {payment.get('amount_usdc')} USDC")
            st.write(f"Status: `{payment.get('state')}`")
            if payment.get("circle_transaction_id"):
                st.write(f"Circle TX: `{payment['circle_transaction_id']}`")
            if payment.get("tx_hash") and payment.get("tx_hash") != "0x" + "0" * 64:
                explorer = f"https://testnet.arcscan.app/tx/{payment['tx_hash']}"
                st.markdown(f"[🔗 View on Arc Explorer]({explorer})")
            st.divider()


# ── Main UI ───────────────────────────────────────────────────────────────────

st.title("🤖 Agent Marketplace")
st.markdown("Complete flow: User → Register → Fund Wallet → Buyer Workflow → Results")

# Create tabs for the flow
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Register User",
    "2️⃣ Setup Agents",
    "3️⃣ Fund Wallet",
    "4️⃣ Buyer Workflow",
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
    st.header("🔄 Buyer Workflow: Discover, Plan, Pay, Send & Fetch")

    if not st.session_state.current_buyer or not st.session_state.current_seller:
        st.warning("⚠️ Setup both agents in Tab 2 first")
    elif not st.session_state.buyer_wallet_funded:
        st.warning("⚠️ Fund wallet in Tab 3 first")
    else:
        buyer = st.session_state.current_buyer
        seller = st.session_state.current_seller

        st.subheader("📝 Research Query")
        user_goal = st.text_area(
            "What would you like to research?",
            value="What is Arc Testnet and how does it work?",
            height=100,
            key="user_goal"
        )

        if not st.session_state.research_results:
            render_buyer_workflow_panel()

        if st.button("🚀 Start Research Flow", key="btn_start_research", use_container_width=True):
            thread_id = f"demo-{uuid.uuid4().hex[:8]}"

            # Create placeholders for streaming updates
            status_placeholder = st.empty()
            workflow_container = st.container()
            plan_container = st.container()
            payment_container = st.container()

            try:
                status_placeholder.info(
                    "🔄 Buyer agent running: discover seller → plan steps → execute payment → send research → fetch result..."
                )

                # Call the research flow API
                result = api_request(
                    "POST",
                    "/run",
                    {
                        "user_goal": user_goal,
                        "thread_id": thread_id,
                        "buyer_agent_id": buyer["id"],
                        "seller_agent_id": seller["id"]
                    }
                )

                status_placeholder.success(
                    "✅ Buyer agent completed: discover seller → plan steps → execute payment → send research → fetch result"
                )
                with workflow_container:
                    render_buyer_workflow_panel(result)

                with plan_container:
                    render_plan_panel(user_goal, result)

                with payment_container:
                    render_payment_panel(result)

                # Store and show final results
                st.session_state.research_results = result
                st.session_state.research_error = None
                st.rerun()

            except Exception as e:
                st.session_state.research_results = None
                st.session_state.research_error = str(e)
                st.error(f"❌ Error: {e}")

        if st.session_state.research_results:
            st.subheader("📌 Most Recent Run")
            render_buyer_workflow_panel(st.session_state.research_results)
            render_plan_panel(user_goal, st.session_state.research_results)
            render_payment_panel(st.session_state.research_results)
        elif st.session_state.research_error:
            st.error(f"❌ {st.session_state.research_error}")


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

        # Payments with proof
        payments = result.get("payments", [])
        if payments:
            st.subheader(f"💳 Payments ({len(payments)})")
            for i, payment in enumerate(payments, 1):
                with st.expander(f"Payment {i}: {payment.get('task_id')} - {payment.get('state')}"):
                    st.write(f"**Amount:** {payment.get('amount_usdc')} USDC")
                    st.write(f"**Status:** {payment.get('state')}")

                    # Circle Transaction ID
                    circle_tx = payment.get('circle_transaction_id', '')
                    if circle_tx:
                        st.write(f"**Circle Transaction ID:** `{circle_tx}`")

                    # On-chain TX Hash with explorer link
                    tx_hash = payment.get('tx_hash', '')
                    if tx_hash and tx_hash != '0x' + '0' * 64:
                        st.write(f"**On-Chain TX Hash:** `{tx_hash}`")
                        explorer_url = f"https://testnet.arcscan.app/tx/{tx_hash}"
                        st.markdown(f"[🔍 View on Arc Explorer]({explorer_url})")
                    else:
                        st.write("**On-Chain TX Hash:** Pending confirmation...")

        # Transaction Hashes
        tx_hashes = result.get("transaction_hashes", [])
        if tx_hashes:
            st.subheader(f"🔗 On-Chain Transactions ({len(tx_hashes)})")
            for tx_hash in tx_hashes:
                if tx_hash and tx_hash != '0x' + '0' * 64:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.code(tx_hash)
                    with col2:
                        explorer_url = f"https://testnet.arcscan.app/tx/{tx_hash}"
                        st.markdown(f"[View ↗]({explorer_url})")

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
4. Run buyer workflow
5. View results & payments
""")
