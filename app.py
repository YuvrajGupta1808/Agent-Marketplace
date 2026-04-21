from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import patch

import httpx
import streamlit as st
from fastapi.testclient import TestClient

from api.server import app as api_app
from seller_agent.server import app as seller_app
from shared.config import get_settings

st.set_page_config(
    page_title="Agent Marketplace",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def initialize_state() -> None:
    st.session_state.setdefault("created_users", [])
    st.session_state.setdefault("created_agents", [])
    st.session_state.setdefault("active_user", None)
    st.session_state.setdefault("active_buyer", None)
    st.session_state.setdefault("active_seller", None)
    st.session_state.setdefault("last_run", None)


class SellerProxy:
    def __init__(self, *_: Any, **__: Any) -> None:
        self._inner = TestClient(seller_app)

    def __enter__(self) -> TestClient:
        self._inner.__enter__()
        return self._inner

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return self._inner.__exit__(exc_type, exc, tb)


@contextmanager
def embedded_client() -> Iterator[TestClient]:
    with patch("httpx.Client", SellerProxy):
        with TestClient(api_app, raise_server_exceptions=False) as client:
            yield client


def api_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    mode: str,
    api_base_url: str,
) -> dict[str, Any]:
    if mode == "Embedded":
        with embedded_client() as client:
            response = client.request(method, path, json=payload)
    else:
        with httpx.Client(
            base_url=api_base_url.rstrip("/"),
            timeout=get_settings().request_timeout_seconds,
        ) as client:
            response = client.request(method, path, json=payload)

    if response.status_code >= 400:
        try:
            body = response.json()
            detail = body.get("detail") or body.get("message") or response.text
        except Exception:
            detail = response.text
        raise RuntimeError(f"HTTP {response.status_code}: {detail}")

    response.raise_for_status()
    return response.json()


def upsert_user(user: dict[str, Any]) -> None:
    st.session_state.created_users = [
        u for u in st.session_state.created_users if u["id"] != user["id"]
    ] + [user]
    st.session_state.active_user = user["id"]


def upsert_agent(agent: dict[str, Any]) -> None:
    st.session_state.created_agents = [
        a for a in st.session_state.created_agents if a["id"] != agent["id"]
    ] + [agent]
    if agent["role"] == "buyer":
        st.session_state.active_buyer = agent["id"]
    if agent["role"] == "seller":
        st.session_state.active_seller = agent["id"]


def find_user(user_id: str | None) -> dict[str, Any] | None:
    if not user_id:
        return None
    return next((u for u in st.session_state.created_users if u["id"] == user_id), None)


def find_agent(agent_id: str | None) -> dict[str, Any] | None:
    if not agent_id:
        return None
    return next((a for a in st.session_state.created_agents if a["id"] == agent_id), None)


def provision_agent(role: str, name: str, mode: str, api_base_url: str) -> dict[str, Any]:
    return api_request(
        "POST",
        "/agents",
        {
            "user_id": st.session_state.active_user,
            "role": role,
            "name": name,
            "endpoint_url": None,
        },
        mode,
        api_base_url,
    )


# ── sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(mode: str, api_base_url: str) -> None:
    settings = get_settings()

    st.header("Status")
    st.write(f"**Mode:** {mode}")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Circle", "✅ On" if settings.circle_enabled else "❌ Off")
    with col2:
        st.metric("LLM", "✅ Live" if settings.live_llm_enabled else "⚠️ Stub")

    st.divider()
    st.header("Progress")

    user = find_user(st.session_state.active_user)
    buyer = find_agent(st.session_state.active_buyer)
    seller = find_agent(st.session_state.active_seller)
    run = st.session_state.last_run

    def step(n: int, label: str, done: bool, detail: str = "") -> None:
        icon = "✅" if done else "⬜"
        text = f"{icon} **{n}. {label}**"
        if detail:
            text += f"  \n`{detail}`"
        st.markdown(text)

    step(1, "User", bool(user), user["display_name"] if user else "")
    if buyer:
        addr = buyer["wallet"]["address"]
        step(2, "Buyer", True, f"{buyer['name']} · {addr[:6]}…{addr[-4:]}")
    else:
        step(2, "Buyer", False, "")
    if seller:
        addr = seller["wallet"]["address"]
        step(3, "Research Agent", True, f"{seller['name']} · {addr[:6]}…{addr[-4:]}")
    else:
        step(3, "Research Agent", False, "")
    step(4, "Run", bool(run), run["thread_id"] if run else "")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    initialize_state()

    with st.sidebar:
        st.title("⚙️ Settings")
        mode = st.radio("Execution mode", ["Embedded", "Remote API"])
        api_base_url = st.text_input("API base URL", value="http://127.0.0.1:8000")
        st.divider()
        render_sidebar(mode, api_base_url)

    st.title("🤖 Agent Marketplace Demo")
    st.caption("Buyer agent pays a research agent via Circle wallets on Arc Testnet.")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1 — User
    # ─────────────────────────────────────────────────────────────────────────
    st.header("1. Create User")
    with st.form("create-user"):
        col1, col2 = st.columns(2)
        with col1:
            display_name = st.text_input("Display name", placeholder="Yuvraj")
        with col2:
            external_id = st.text_input("External ID (optional)", placeholder="demo-01")
        if st.form_submit_button("Create user", use_container_width=True):
            if not display_name.strip():
                st.error("Display name is required.")
            else:
                try:
                    data = api_request(
                        "POST",
                        "/users",
                        {"display_name": display_name.strip(), "external_id": external_id.strip() or None},
                        mode,
                        api_base_url,
                    )
                    upsert_user(data["user"])
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.created_users:
        options = {
            f"{u['display_name']} ({u['id'][:8]})": u["id"]
            for u in st.session_state.created_users
        }
        selected = st.selectbox(
            "Active user",
            list(options.keys()),
            index=(
                max(0, list(options.values()).index(st.session_state.active_user))
                if st.session_state.active_user in options.values()
                else 0
            ),
            key="user_select",
        )
        if st.session_state.active_user != options[selected]:
            st.session_state.active_user = options[selected]
            st.rerun()

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2 — Provision agents
    # ─────────────────────────────────────────────────────────────────────────
    st.header("2. Provision Agents")

    if not st.session_state.active_user:
        st.info("Create a user first.")
    else:
        # ── Quick Research Setup ──────────────────────────────────────────────
        buyer_ready = bool(st.session_state.active_buyer)
        seller_ready = bool(st.session_state.active_seller)

        if not buyer_ready or not seller_ready:
            with st.container(border=True):
                st.subheader("🔬 Quick Research Setup")
                st.caption(
                    "Provisions a **Buyer** agent and a **Research Agent** (seller) "
                    "with pre-configured Circle wallets — ready to run in one click."
                )
                col1, col2 = st.columns(2)
                with col1:
                    quick_buyer_name = st.text_input(
                        "Buyer name", value="Research Buyer", key="quick_buyer_name"
                    )
                with col2:
                    quick_seller_name = st.text_input(
                        "Research Agent name", value="Arc Research Agent", key="quick_seller_name"
                    )

                if st.button("⚡ Provision Research Agent Pair", use_container_width=True, type="primary"):
                    errors = []
                    with st.spinner("Provisioning agents…"):
                        if not buyer_ready:
                            try:
                                data = provision_agent("buyer", quick_buyer_name.strip() or "Research Buyer", mode, api_base_url)
                                upsert_agent(data["agent"])
                                buyer_ready = True
                            except Exception as exc:
                                errors.append(f"Buyer: {exc}")

                        if not seller_ready:
                            try:
                                data = provision_agent("seller", quick_seller_name.strip() or "Arc Research Agent", mode, api_base_url)
                                upsert_agent(data["agent"])
                                seller_ready = True
                            except Exception as exc:
                                errors.append(f"Research Agent: {exc}")

                    for err in errors:
                        st.error(err)
                    if not errors:
                        st.rerun()

        if buyer_ready and seller_ready:
            buyer = find_agent(st.session_state.active_buyer)
            seller = find_agent(st.session_state.active_seller)
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"✅ Buyer: **{buyer['name']}**")
                if buyer:
                    st.caption(f"`{buyer['wallet']['address']}`")
            with col2:
                st.success(f"✅ Research Agent: **{seller['name']}**")
                if seller:
                    st.caption(f"`{seller['wallet']['address']}`")

        # ── Manual provisioning (advanced) ────────────────────────────────────
        with st.expander("➕ Provision a custom agent manually"):
            with st.form("create-agent"):
                col1, col2 = st.columns(2)
                with col1:
                    role = st.selectbox("Role", ["buyer", "seller"])
                with col2:
                    name = st.text_input("Agent name", placeholder="My Research Agent")
                endpoint_url = st.text_input(
                    "Endpoint URL (optional)",
                    placeholder="Leave blank for default",
                )
                if st.form_submit_button("Provision wallet", use_container_width=True):
                    if not name.strip():
                        st.error("Agent name is required.")
                    else:
                        try:
                            with st.spinner("Provisioning Circle wallet…"):
                                data = api_request(
                                    "POST",
                                    "/agents",
                                    {
                                        "user_id": st.session_state.active_user,
                                        "role": role,
                                        "name": name.strip(),
                                        "endpoint_url": endpoint_url.strip() or None,
                                    },
                                    mode,
                                    api_base_url,
                                )
                            upsert_agent(data["agent"])
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

        # Active agent selectors (shown when multiple exist)
        active_user_id = st.session_state.active_user
        active_agents = [a for a in st.session_state.created_agents if a["user_id"] == active_user_id]
        buyers = [a for a in active_agents if a["role"] == "buyer"]
        sellers = [a for a in active_agents if a["role"] == "seller"]

        if len(buyers) > 1 or len(sellers) > 1:
            col1, col2 = st.columns(2)
            with col1:
                if len(buyers) > 1:
                    buyer_opts = {f"{a['name']} ({a['wallet']['address'][:6]}…)": a["id"] for a in buyers}
                    chosen = st.selectbox("Active buyer", list(buyer_opts.keys()), key="buyer_select")
                    st.session_state.active_buyer = buyer_opts[chosen]
            with col2:
                if len(sellers) > 1:
                    seller_opts = {f"{a['name']} ({a['wallet']['address'][:6]}…)": a["id"] for a in sellers}
                    chosen = st.selectbox("Active research agent", list(seller_opts.keys()), key="seller_select")
                    st.session_state.active_seller = seller_opts[chosen]

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3 — Run
    # ─────────────────────────────────────────────────────────────────────────
    st.header("3. Run Research Flow")

    if not st.session_state.active_buyer or not st.session_state.active_seller:
        st.info("Provision a buyer and research agent pair above.")
    else:
        buyer = find_agent(st.session_state.active_buyer)
        seller = find_agent(st.session_state.active_seller)

        if buyer and seller:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Buyer wallet", f"{buyer['wallet']['address'][:8]}…")
                st.caption(f"`{buyer['wallet']['address']}`")
            with col2:
                st.metric("Research Agent wallet", f"{seller['wallet']['address'][:8]}…")
                st.caption(f"`{seller['wallet']['address']}`")
            with col3:
                st.metric("Chain", buyer["wallet"]["blockchain"])
            with col4:
                st.metric("Status", "⚠️ Unfunded")
                st.link_button(
                    "🔗 Fund at Faucet",
                    "https://faucet.circle.com",
                    use_container_width=True,
                )

            st.info(
                "**Buyer wallet funding required:** Head to the Circle Testnet Faucet and paste your buyer wallet address "
                f"(`{buyer['wallet']['address']}`) to receive test USDC. You need at least 0.001 USDC per research query."
            )

        with st.form("run-marketplace"):
            # Debug info
            with st.expander("ℹ️ Debug / Agent IDs"):
                st.write(f"**Buyer ID:** `{st.session_state.active_buyer}`")
                st.write(f"**Seller ID:** `{st.session_state.active_seller}`")

            user_goal = st.text_area(
                "Research goal",
                value="Research the top 3 DeFi protocols on Arc and explain why low-fee programmable money matters.",
                height=100,
            )
            thread_id = st.text_input("Thread ID", value=f"demo-{uuid.uuid4().hex[:8]}")
            if st.form_submit_button("▶ Run paid research", use_container_width=True, type="primary"):
                if not user_goal.strip():
                    st.error("Research goal is required.")
                elif not st.session_state.active_buyer or not st.session_state.active_seller:
                    st.error("❌ Buyer and seller agents must be provisioned first.")
                else:
                    try:
                        with st.spinner("Buyer → pays → Research Agent → synthesizes…"):
                            data = api_request(
                                "POST",
                                "/run",
                                {
                                    "user_goal": user_goal.strip(),
                                    "thread_id": thread_id.strip(),
                                    "buyer_agent_id": st.session_state.active_buyer,
                                    "seller_agent_id": st.session_state.active_seller,
                                },
                                mode,
                                api_base_url,
                            )
                        st.session_state.last_run = data
                        st.rerun()
                    except Exception as exc:
                        st.error(f"❌ Error: {str(exc)}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4 — Results
    # ─────────────────────────────────────────────────────────────────────────
    run = st.session_state.last_run
    if run:
        st.divider()
        st.header("4. Research Results")
        st.caption(f"Thread: `{run['thread_id']}`")

        # Show final answer prominently
        final_answer = run.get("final_answer")
        if final_answer:
            st.subheader("📋 Combined Research Answer")
            with st.container(border=True):
                st.markdown(final_answer)
        else:
            st.info("No final answer yet — check payment status or wait for synthesis.")

        # ── Payment records ───────────────────────────────────────────────────
        payments = run.get("payments") or []
        tx_hashes = run.get("transaction_hashes") or []

        if payments or tx_hashes:
            st.subheader("💸 Payments")
            settings = get_settings()

            if payments:
                for pmt in payments:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.caption("Circle Transaction ID")
                            st.code(pmt["circle_transaction_id"], language=None)
                        with col2:
                            st.caption("Amount · Status")
                            state_icon = "✅" if pmt["state"] == "CONFIRMED" else "⏳"
                            st.write(f"**{pmt['amount_usdc']} USDC** {state_icon} {pmt['state']}")
                            if pmt.get("tx_hash"):
                                st.caption(f"On-chain: `{pmt['tx_hash']}`")
                                st.link_button(
                                    "View on Arc Explorer",
                                    f"{settings.arc_explorer_url}/tx/{pmt['tx_hash']}",
                                )
                        with col3:
                            st.caption("Check status")
                            if st.button("🔄 Refresh", key=f"refresh_{pmt['circle_transaction_id']}"):
                                try:
                                    status = api_request(
                                        "GET",
                                        f"/payments/{pmt['circle_transaction_id']}",
                                        None,
                                        mode,
                                        api_base_url,
                                    )
                                    updated_state = status.get("state", pmt["state"])
                                    updated_hash = status.get("tx_hash") or pmt.get("tx_hash")
                                    # Patch the run's payment record in session state
                                    for p in st.session_state.last_run["payments"]:
                                        if p["circle_transaction_id"] == pmt["circle_transaction_id"]:
                                            p["state"] = updated_state
                                            if updated_hash:
                                                p["tx_hash"] = updated_hash
                                                if updated_hash not in st.session_state.last_run.get("transaction_hashes", []):
                                                    st.session_state.last_run.setdefault("transaction_hashes", []).append(updated_hash)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))
            elif tx_hashes:
                # Fallback: just show raw tx hashes (legacy path)
                for tx in tx_hashes:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.code(tx, language=None)
                    with col2:
                        st.link_button("Explorer", f"{settings.arc_explorer_url}/tx/{tx}")
        else:
            st.info(
                "No payment records returned — this happens when Circle keys are missing "
                "or the flow ran in stub mode."
            )

        failed = run.get("failed_tasks") or []
        if failed:
            st.warning(f"Failed tasks: {', '.join(failed)}")

        if run.get("pending_question"):
            st.info(f"Clarification needed: **{run['pending_question']}**")
            with st.form("resume"):
                answer_text = st.text_input("Your answer")
                if st.form_submit_button("Resume flow"):
                    try:
                        data = api_request(
                            "POST",
                            "/resume",
                            {"thread_id": run["thread_id"], "answer": answer_text},
                            mode,
                            api_base_url,
                        )
                        st.session_state.last_run = data
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


if __name__ == "__main__":
    main()
