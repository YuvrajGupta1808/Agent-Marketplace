from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, START, StateGraph

from buyer_agent.nodes.discover import discover_seller
from buyer_agent.nodes.fetch_result import fetch_result
from buyer_agent.nodes.pay import execute_payment
from buyer_agent.nodes.plan import plan_research_steps
from buyer_agent.nodes.send_research import send_research_request
from buyer_agent.state import BuyerState
from shared.types import GraphNodeOutput


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


def execute_buyer_graph_with_trace(initial_state: BuyerState) -> tuple[BuyerState, list[GraphNodeOutput]]:
    """Run the buyer graph nodes in graph order while capturing state snapshots and timing."""
    state: BuyerState = dict(initial_state)
    trace: list[GraphNodeOutput] = []
    node_sequence = [
        ("discover_seller", "Discover Seller", "planning", discover_seller),
        ("plan_research_steps", "ReAct: Reason", "planning", plan_research_steps),
        ("execute_payment", "Execute Payment", "execute", execute_payment),
        ("send_research_request", "Send Research", "execute", send_research_request),
        ("fetch_result", "Fetch Result", "execute", fetch_result),
    ]

    for node_name, title, phase, node_fn in node_sequence:
        input_state = dict(state)
        start_time = time.time()
        output = node_fn(state)
        duration_ms = int((time.time() - start_time) * 1000)
        state.update(output)

        thinking = output.get("thinking", "")
        status = "done" if not output.get("error") else "error"

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
                state_after=_snapshot(dict(state)),
            )
        )
        if output.get("error"):
            break

    return state, trace

builder = StateGraph(BuyerState)
builder.add_node("discover_seller", discover_seller)
builder.add_node("plan_research_steps", plan_research_steps)
builder.add_node("execute_payment", execute_payment)
builder.add_node("send_research_request", send_research_request)
builder.add_node("fetch_result", fetch_result)
builder.add_edge(START, "discover_seller")
builder.add_edge("discover_seller", "plan_research_steps")
builder.add_edge("plan_research_steps", "execute_payment")
builder.add_edge("execute_payment", "send_research_request")
builder.add_edge("send_research_request", "fetch_result")
builder.add_edge("fetch_result", END)

buyer_graph = builder.compile()
