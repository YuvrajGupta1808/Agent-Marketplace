#!/usr/bin/env python
"""Test buyer agent conditional routing - direct answer vs seller workflow."""

from unittest.mock import patch, MagicMock
from buyer_agent.state import BuyerState

def mock_get_agent(self, agent_id):
    """Mock agent retrieval from database."""
    return MagicMock(
        id=agent_id,
        role="seller",
        wallet_id="mock-wallet-id",
        wallet=MagicMock(address="0xmockaddress"),
    )

# Patch repository.get_agent before importing execute_buyer_graph_with_trace
with patch("shared.repository.MarketplaceRepository.get_agent", mock_get_agent):
    from buyer_agent.graph import execute_buyer_graph_with_trace

    # Test 1: Simple greeting - should get direct answer, no seller workflow
    print("Test 1: Greeting query (should NOT involve seller)")
    print("=" * 80)
    state: BuyerState = {
        "task_id": "test-1",
        "query": "Hi, how are you?",
        "buyer_agent_id": "buyer-123",
        "seller_agent_id": "seller-123",
        "thread_id": "thread-1",
    }

    final_state, trace = execute_buyer_graph_with_trace(state)

    print(f"\n📊 Trace Summary:")
    for node in trace:
        print(f"  - {node.node_name:30} | {node.title:30} | {node.status}")

    print(f"\n✅ Result:")
    print(f"  Needs external research: {final_state.get('needs_external_research')}")
    print(f"  Direct answer: {final_state.get('direct_answer')[:100] if final_state.get('direct_answer') else 'N/A'}")
    if final_state.get('result'):
        result = final_state.get('result', {})
        print(f"  Result title: {result.get('title', 'N/A')[:60]}")
        print(f"  Result summary: {result.get('summary', 'N/A')[:100]}")
        print(f"  Seller name: {result.get('seller_name', 'N/A')}")

    print(f"\n❓ Should have nodes: discover_seller, plan_research_steps, evaluate_research_need, format_direct_answer")
    node_names = [n.node_name for n in trace]
    print(f"   Actual nodes: {', '.join(node_names)}")
    print(f"   ✓ No payment/seller nodes!" if "execute_payment" not in node_names else "   ❌ Unexpectedly has payment/seller nodes")

    # Test 2: Research-heavy query - should go through full seller workflow
    print("\n" + "=" * 80)
    print("Test 2: Current events query (SHOULD involve seller workflow)")
    print("=" * 80)
    state = {
        "task_id": "test-2",
        "query": "What are the latest AI developments in 2026?",
        "buyer_agent_id": "buyer-123",
        "seller_agent_id": "seller-123",
        "thread_id": "thread-2",
    }

    final_state, trace = execute_buyer_graph_with_trace(state)

    print(f"\n📊 Trace Summary:")
    for node in trace:
        print(f"  - {node.node_name:30} | {node.title:30} | {node.status}")

    print(f"\n✅ Result:")
    print(f"  Needs external research: {final_state.get('needs_external_research')}")
    if final_state.get('result'):
        result = final_state.get('result', {})
        print(f"  Result title: {result.get('title', 'N/A')[:60]}")
        print(f"  Seller name: {result.get('seller_name', 'N/A')}")

    print(f"\n❓ Should have nodes: discover_seller, plan_research_steps, evaluate_research_need, execute_payment, send_research_request, fetch_result")
    node_names = [n.node_name for n in trace]
    print(f"   Actual nodes: {', '.join(node_names)}")
    expected_nodes = {"discover_seller", "plan_research_steps", "evaluate_research_need", "execute_payment", "send_research_request", "fetch_result"}
    has_payment = "execute_payment" in node_names
    print(f"   {'✓' if has_payment else '❌'} Has payment/seller nodes as expected")
