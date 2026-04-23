from __future__ import annotations

from langgraph.types import Send

from orchestrator.state import OrchestratorState


def route_from_planner(state: OrchestratorState):
    if state.get("pending_question"):
        print(f"\n🛣️ route_from_planner: pending question → ask_clarification")
        return "ask_clarification"

    task_specs = state.get("task_specs", [])
    if not task_specs:
        print(f"\n🛣️ route_from_planner: no tasks → synthesize_answer")
        return "synthesize_answer"

    print(f"\n🛣️ route_from_planner: {len(task_specs)} task(s) → buyer_agent_node")
    return [
        Send(
            "buyer_agent_node",
            {
                "task_id": spec.task_id,
                "query": spec.query,
                "buyer_agent_id": state["buyer_agent_id"],
                "seller_agent_id": state["seller_agent_id"],
            },
        )
        for spec in task_specs
    ]
