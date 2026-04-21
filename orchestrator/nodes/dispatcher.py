from __future__ import annotations

from langgraph.types import Send

from orchestrator.state import OrchestratorState


def route_from_planner(state: OrchestratorState):
    if state.get("pending_question"):
        return "ask_clarification"
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
        for spec in state.get("task_specs", [])
    ]
