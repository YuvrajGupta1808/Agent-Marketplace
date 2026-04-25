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
        start_time = time.time()

        if writer:
            writer({
                "event_type": "node_start",
                "task_id": task_id,
                "node": node_name,
                "title": title,
                "query": query,
            })

        output = node_fn(node_state)
        duration_ms = int((time.time() - start_time) * 1000)

        thinking = output.get("thinking", "")
        status = "done" if not output.get("error") else "error"

        if writer:
            writer({
                "event_type": "node_complete",
                "task_id": task_id,
                "node": node_name,
                "title": title,
                "status": status,
                "duration_ms": duration_ms,
            })

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
                state_after=_snapshot(dict(node_state)),
            )
        )

        if output.get("error"):
            if writer:
                writer({
                    "event_type": "error",
                    "task_id": task_id,
                    "node": node_name,
                    "error": output.get("error"),
                })

        return output

    # Step 1: Validate scope
    output = _run_node("validate_scope", "Validate Scope", "routing", validate_scope)
    state.update(output)

    if not state.get("within_scope", True):
        # Out of scope - build rejection result and return
        state["result"] = _build_rejection_result(state)
        return state, trace

    # Step 2: Decompose goal into tasks
    output = _run_node("decompose_goal", "Decompose Goal", "planning", decompose_goal)
    state.update(output)

    tasks = state.get("tasks", [])
    task_results = []

    # Step 3: Execute each task
    for task_idx, task in enumerate(tasks, 1):
        task_state = {**state, "task_id": task.get("task_id", f"task-{task_idx}"), "query": task.get("query", "")}

        # 3a. Discover seller (from connected_seller_ids)
        output = _run_node(f"discover_seller_{task_idx}", f"Discover Seller (Task {task_idx})", "planning", discover_seller, task_state)
        task_state.update(output)

        # 3b. Execute payment
        output = _run_node(f"execute_payment_{task_idx}", f"Execute Payment (Task {task_idx})", "execute", execute_payment, task_state)
        task_state.update(output)

        # 3c. Send research request
        output = _run_node(f"send_research_{task_idx}", f"Send Research (Task {task_idx})", "execute", send_research_request, task_state)
        task_state.update(output)

        # 3d. Fetch result
        output = _run_node(f"fetch_result_{task_idx}", f"Fetch Result (Task {task_idx})", "execute", fetch_result, task_state)
        task_state.update(output)

        if task_state.get("result"):
            task_results.append(task_state["result"])

    state["task_results"] = task_results

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
