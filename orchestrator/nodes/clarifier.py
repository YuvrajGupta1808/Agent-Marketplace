from __future__ import annotations

from langgraph.types import interrupt

from orchestrator.state import OrchestratorState


def ask_clarification(state: OrchestratorState) -> dict:
    answer = interrupt({"question": state["pending_question"]})
    return {
        "clarification_answer": answer,
        "pending_question": None,
    }

