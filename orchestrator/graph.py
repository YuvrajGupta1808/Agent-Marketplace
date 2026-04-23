from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from buyer_agent.graph import execute_buyer_graph_with_trace
from orchestrator.nodes.clarifier import ask_clarification
from orchestrator.nodes.dispatcher import route_from_planner
from orchestrator.nodes.planner import plan_tasks
from orchestrator.nodes.synthesizer import synthesize_answer
from orchestrator.state import OrchestratorState
from shared.repository import repository
from shared.types import BuyerWorkflowRecord, PaymentRecord, ResearchResult


def buyer_agent_node(state: dict) -> dict:
    print(f"\n🤖 buyer_agent_node: task_id={state['task_id']}, query={state['query'][:50]}")
    buyer_agent = repository.get_agent(state["buyer_agent_id"])
    result, trace = execute_buyer_graph_with_trace(
        {
            "task_id": state["task_id"],
            "query": state["query"],
            "retry_count": 0,
            "buyer_agent_id": state["buyer_agent_id"],
            "buyer_wallet_id": buyer_agent.wallet.circle_wallet_id,
            "buyer_wallet_address": buyer_agent.wallet.address,
            "seller_agent_id": state["seller_agent_id"],
        },
    )
    buyer_workflows = [
        BuyerWorkflowRecord(
            task_id=state["task_id"],
            execution_plan=result.get("execution_plan", []),
            node_outputs=trace,
        )
    ]
    if result.get("error"):
        return {
            "buyer_workflows": buyer_workflows,
            "failed_tasks": [state["task_id"]],
            "payments": [],
        }

    research_result = ResearchResult.model_validate(result["result"])
    tx_hash = research_result.tx_hash

    payments = []
    if research_result.circle_transaction_id:
        payments.append(
            PaymentRecord(
                task_id=research_result.task_id,
                circle_transaction_id=research_result.circle_transaction_id,
                amount_usdc=research_result.amount_usdc or "0",
                tx_hash=tx_hash,
                state="CONFIRMED" if tx_hash else "INITIATED",
            )
        )

    return {
        "results": [research_result],
        "buyer_workflows": buyer_workflows,
        "transaction_hashes": [tx_hash] if tx_hash else [],
        "payments": payments,
        "failed_tasks": [],
    }


builder = StateGraph(OrchestratorState)
builder.add_node("plan_tasks", plan_tasks)
builder.add_node("ask_clarification", ask_clarification)
builder.add_node("buyer_agent_node", buyer_agent_node)
builder.add_node("synthesize_answer", synthesize_answer)
builder.add_edge(START, "plan_tasks")
builder.add_conditional_edges("plan_tasks", route_from_planner)
builder.add_edge("ask_clarification", "plan_tasks")
builder.add_edge("buyer_agent_node", "synthesize_answer")
builder.add_edge("synthesize_answer", END)

orchestrator_graph = builder.compile(checkpointer=InMemorySaver())
