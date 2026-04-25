from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.config import get_stream_writer

from buyer_agent.nodes.decompose_goal import decompose_goal
from buyer_agent.nodes.discover import discover_seller
from buyer_agent.nodes.fetch_result import fetch_result
from buyer_agent.nodes.pay import execute_payment
from buyer_agent.nodes.send_research import send_research_request
from buyer_agent.nodes.synthesize_results import synthesize_results
from buyer_agent.nodes.validate_scope import validate_scope
from buyer_agent.state import BuyerState
from shared.types import GraphNodeOutput, ResearchResult


def _snapshot(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _snapshot(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _snapshot(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_snapshot(item) for item in value]
    if isinstance(value, tuple):
        return [_snapshot(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _build_rejection_result(state: BuyerState) -> dict:
    """Build a rejection result when goal is out of scope."""
    agent_name = state.get("buyer_agent_name", "Agent")
    rejection_reason = state.get("scope_rejection_reason", "This goal is outside my capabilities.")

    result = ResearchResult(
        task_id=state.get("task_id", "scope-rejection"),
        title=f"{agent_name} — Out of Scope",
        summary=rejection_reason,
        bullets=[
            "Please try a different buyer agent.",
            "Or add a seller agent that handles this capability.",
        ],
        seller_name=agent_name,
        is_ambiguous=False,
    )
    return result.model_dump()


def execute_buyer_graph_with_trace(initial_state: BuyerState) -> tuple[BuyerState, list[GraphNodeOutput]]:
    """
    Run the autonomous buyer agent graph.

    Flow:
    1. validate_scope - check if goal is within agent's capabilities
    2. If out of scope - return rejection, else continue
    3. decompose_goal - break goal into tasks
    4. For each task: discover_seller → execute_payment → send_research_request → fetch_result
    5. synthesize_results - combine all results
    """
    state: BuyerState = dict(initial_state)
    trace: list[GraphNodeOutput] = []
    task_id = initial_state.get("task_id", "unknown")
    query = initial_state.get("query", initial_state.get("user_goal", ""))[:60]

    try:
        writer = get_stream_writer()
    except (RuntimeError, AttributeError):
        writer = None

    def _run_node(node_name: str, title: str, phase: str, node_fn, node_state: BuyerState | None = None) -> dict:
        """Execute a single node and record trace."""
        if node_state is None:
            node_state = state

        input_state = dict(node_state)
        event_task_id = node_state.get("task_id", task_id)
        start_time = time.time()

        if writer:
            writer({
                "event_type": "node_start",
                "task_id": event_task_id,
                "node": node_name,
                "title": title,
                "query": node_state.get("query", query),
            })

        try:
            output = node_fn(node_state) or {}
        except Exception as exc:
            output = {"error": f"{type(exc).__name__}: {exc}"}
        duration_ms = int((time.time() - start_time) * 1000)

        thinking = output.get("thinking", "")
        status = "done" if not output.get("error") else "error"

        if writer:
            complete_event = {
                "event_type": "node_complete",
                "task_id": event_task_id,
                "node": node_name,
                "title": title,
                "status": status,
                "duration_ms": duration_ms,
            }
            if output.get("error"):
                complete_event["error"] = output["error"]
            if output.get("payment_receipt"):
                complete_event["payment_details"] = output["payment_receipt"]
            if output.get("result"):
                complete_event["research_result"] = output["result"]
            writer(complete_event)

        state_after = dict(node_state)
        state_after.update(output)

        trace.append(
            GraphNodeOutput(
                node_name=node_name,
                title=title,
                phase=phase,
                status=status,
                duration_ms=duration_ms,
                reasoning=thinking,
                input_state=_snapshot(input_state),
                output=_snapshot(output),
                state_after=_snapshot(state_after),
            )
        )

        if output.get("error"):
            if writer:
                writer({
                    "event_type": "error",
                    "task_id": event_task_id,
                    "node": node_name,
                    "error": output.get("error"),
                })

        return output

    def _record_task_error(task_errors: list[dict[str, Any]], task_state: BuyerState, node_name: str, title: str, output: dict) -> None:
        message = str(output.get("error") or "Unknown task error")
        task_errors.append(
            {
                "task_id": task_state.get("task_id", "unknown"),
                "query": task_state.get("query", ""),
                "node": node_name,
                "title": title,
                "message": message,
            }
        )

    # Step 1: Validate scope
    output = _run_node("validate_scope", "Validate Scope", "routing", validate_scope)
    state.update(output)

    if not state.get("within_scope", True):
        # Out of scope - ask for clarification instead of auto-rejecting
        query = state.get('query', '')[:30]
        clarification_q = f"Your request about '{query}' seems to be outside my marketplace scope... Could you clarify what you'd like me to help you find through the Agent Marketplace?"
        state["pending_question"] = clarification_q
        state["final_answer"] = None
        return state, trace

    # Step 2: Decompose goal into tasks
    output = _run_node("decompose_goal", "Decompose Goal", "planning", decompose_goal)
    state.update(output)

    tasks = state.get("tasks", [])
    task_results = []
    task_errors: list[dict[str, Any]] = []

    # Step 3: Execute each task
    for task_idx, task in enumerate(tasks, 1):
        task_state = {**state, "task_id": task.get("task_id", f"task-{task_idx}"), "query": task.get("query", "")}

        task_steps = [
            ("discover_seller", f"Discover Seller (Task {task_idx})", "planning", discover_seller),
            ("execute_payment", f"Execute Payment (Task {task_idx})", "execute", execute_payment),
            ("send_research", f"Send Research (Task {task_idx})", "execute", send_research_request),
            ("fetch_result", f"Fetch Result (Task {task_idx})", "execute", fetch_result),
        ]

        task_failed = False
        for base_node_name, title, phase, node_fn in task_steps:
            node_name = f"{base_node_name}_{task_idx}"
            output = _run_node(node_name, title, phase, node_fn, task_state)
            task_state.update(output)

            if output.get("error"):
                _record_task_error(task_errors, task_state, node_name, title, output)
                task_failed = True
                break

        if task_failed:
            continue

        if task_state.get("result"):
            task_results.append(task_state["result"])

    state["task_results"] = task_results
    if task_errors:
        state["task_errors"] = task_errors

    if task_errors and not task_results:
        state["error"] = task_errors[0]["message"]
        return state, trace

    # Step 4: Synthesize results
    output = _run_node("synthesize_results", "Synthesize Results", "synthesis", synthesize_results)
    state.update(output)

    return state, trace


builder = StateGraph(BuyerState)
builder.add_node("validate_scope", validate_scope)
builder.add_node("decompose_goal", decompose_goal)
builder.add_node("discover_seller", discover_seller)
builder.add_node("execute_payment", execute_payment)
builder.add_node("send_research_request", send_research_request)
builder.add_node("fetch_result", fetch_result)
builder.add_node("synthesize_results", synthesize_results)

builder.add_edge(START, "validate_scope")
builder.add_conditional_edges(
    "validate_scope",
    lambda s: "decompose_goal" if s.get("within_scope", True) else END,
)
builder.add_edge("decompose_goal", "discover_seller")
builder.add_edge("discover_seller", "execute_payment")
builder.add_edge("execute_payment", "send_research_request")
builder.add_edge("send_research_request", "fetch_result")
builder.add_edge("fetch_result", "synthesize_results")
builder.add_edge("synthesize_results", END)

buyer_graph = builder.compile()
