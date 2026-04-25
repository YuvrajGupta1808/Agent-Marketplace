from __future__ import annotations

import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from buyer_agent.graph import execute_buyer_graph_with_trace
from orchestrator.state import OrchestratorState
from shared.repository import repository
from shared.types import BuyerWorkflowRecord, PaymentRecord, ResearchResult


def _collect_research_results(result: dict) -> list[ResearchResult]:
    records: list[ResearchResult] = []
    for item in result.get("task_results", []):
        try:
            records.append(ResearchResult.model_validate(item))
        except Exception:
            continue
    if not records and result.get("result"):
        try:
            records.append(ResearchResult.model_validate(result["result"]))
        except Exception:
            pass
    return records


def _collect_payments(results: list[ResearchResult]) -> tuple[list[str], list[PaymentRecord]]:
    tx_hashes: list[str] = []
    payments: list[PaymentRecord] = []
    for research_result in results:
        if research_result.tx_hash:
            tx_hashes.append(research_result.tx_hash)
        if research_result.circle_transaction_id:
            payments.append(
                PaymentRecord(
                    task_id=research_result.task_id,
                    circle_transaction_id=research_result.circle_transaction_id,
                    amount_usdc=research_result.amount_usdc or "0",
                    tx_hash=research_result.tx_hash,
                    state="CONFIRMED" if research_result.tx_hash else "INITIATED",
                )
            )
    return tx_hashes, payments


def buyer_agent_node(state: dict) -> dict:
    """Execute autonomous buyer agent for the user goal."""
    print(f"\n🤖 buyer_agent_node: user_goal='{state['user_goal'][:50]}'")
    buyer_agent = repository.get_agent(state["buyer_agent_id"])

    # Extract connected_seller_ids from agent metadata
    connected_seller_ids = state.get("metadata", {}).get("connected_seller_ids", []) if hasattr(state.get("metadata"), "get") else []
    if not connected_seller_ids and isinstance(buyer_agent.metadata, dict):
        connected_seller_ids = buyer_agent.metadata.get("connected_seller_ids", [])

    result, trace = execute_buyer_graph_with_trace(
        {
            "user_goal": state["user_goal"],
            "task_id": str(uuid.uuid4())[:8],
            "query": state["user_goal"],
            "thread_id": state.get("thread_id", "unknown"),
            "buyer_agent_id": state["buyer_agent_id"],
            "buyer_wallet_id": buyer_agent.wallet.circle_wallet_id,
            "buyer_wallet_address": buyer_agent.wallet.address,
            # Identity fields
            "buyer_agent_name": buyer_agent.name,
            "buyer_agent_description": buyer_agent.description,
            "buyer_agent_system_prompt": buyer_agent.system_prompt,
            "buyer_agent_connected_seller_ids": connected_seller_ids,
            "buyer_agent_llm_config": buyer_agent.metadata.get("llm_config", {}) if isinstance(buyer_agent.metadata, dict) else {},
            "buyer_agent_payment_config": buyer_agent.metadata.get("payment_config", {}) if isinstance(buyer_agent.metadata, dict) else {},
            # Backwards compat
            "seller_agent_id": state.get("seller_agent_id"),
        },
    )

    buyer_workflows = [
        BuyerWorkflowRecord(
            task_id=result.get("task_id", ""),
            execution_plan=result.get("execution_plan", []),
            node_outputs=trace,
        )
    ]
    task_errors = result.get("task_errors", [])
    failed_task_ids = [
        str(error.get("task_id", "unknown"))
        for error in task_errors
        if isinstance(error, dict)
    ]

    if result.get("error"):
        return {
            "buyer_workflows": buyer_workflows,
            "failed_tasks": failed_task_ids or [result.get("task_id", "unknown")],
            "payments": [],
            "transaction_hashes": [],
            "results": [],
            "final_answer": None,
            "error": result["error"],
        }

    # If we have a final_answer (from synthesize_results), use it
    final_answer = result.get("final_answer")
    if final_answer:
        research_results = _collect_research_results(result)
        tx_hashes, payments = _collect_payments(research_results)
        return {
            "buyer_workflows": buyer_workflows,
            "payments": payments,
            "transaction_hashes": tx_hashes,
            "results": research_results,
            "final_answer": final_answer,
            "failed_tasks": failed_task_ids,
        }

    # Otherwise, extract result if it exists
    if result.get("result"):
        research_result = ResearchResult.model_validate(result["result"])
        tx_hashes, payments = _collect_payments([research_result])

        return {
            "results": [research_result],
            "buyer_workflows": buyer_workflows,
            "transaction_hashes": tx_hashes,
            "payments": payments,
            "failed_tasks": failed_task_ids,
            "final_answer": None,
        }

    return {
        "buyer_workflows": buyer_workflows,
        "failed_tasks": failed_task_ids,
        "payments": [],
        "transaction_hashes": [],
        "results": [],
        "final_answer": None,
    }


builder = StateGraph(OrchestratorState)
builder.add_node("buyer_agent_node", buyer_agent_node)
builder.add_edge(START, "buyer_agent_node")
builder.add_edge("buyer_agent_node", END)

orchestrator_graph = builder.compile(checkpointer=InMemorySaver())
