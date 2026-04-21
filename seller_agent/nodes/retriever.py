from __future__ import annotations

from seller_agent.state import SellerState


def retrieve_context(state: SellerState) -> dict:
    query = state["query"]
    citations = [
        {
            "title": "Connect to Arc",
            "url": "https://docs.arc.network/arc/references/connect-to-arc",
            "snippet": "Arc Testnet uses chain id 5042002, RPC https://rpc.testnet.arc.network, and USDC as the gas token.",
        },
        {
            "title": "Contract addresses",
            "url": "https://docs.arc.network/arc/references/contract-addresses",
            "snippet": "USDC on Arc Testnet is exposed at 0x3600000000000000000000000000000000000000 via an ERC-20 interface.",
        },
        {
            "title": "Developer-controlled wallets Python SDK",
            "url": "https://developers.circle.com/sdks/developer-controlled-wallets-python-sdk",
            "snippet": "Circle's Python SDK initializes with api_key and entity_secret and supports ARC-TESTNET wallets.",
        },
    ]
    return {"retrieval_context": citations, "draft_summary": f"Collected baseline context for: {query}"}

