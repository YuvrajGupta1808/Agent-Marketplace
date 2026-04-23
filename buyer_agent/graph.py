from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.config import get_stream_writer

from buyer_agent.nodes.discover import discover_seller
from buyer_agent.nodes.evaluate_need import evaluate_research_need
from buyer_agent.nodes.fetch_result import fetch_result
from buyer_agent.nodes.format_direct_answer import format_direct_answer
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
    """Run the buyer graph nodes with conditional routing based on research need."""
    state: BuyerState = dict(initial_state)
    trace: list[GraphNodeOutput] = []
    task_id = initial_state.get("task_id", "unknown")
    query = initial_state.get("query", "")[:60]

    try:
        writer = get_stream_writer()
    except (RuntimeError, AttributeError):
        writer = None

    # Initial nodes: discover, plan, evaluate
    initial_nodes = [
        ("discover_seller", "Discover Seller", "planning", discover_seller),
        ("plan_research_steps", "ReAct: Reason", "planning", plan_research_steps),
        ("evaluate_research_need", "Check: Need Research?", "planning", evaluate_research_need),
    ]

    # Execute initial nodes
    for node_name, title, phase, node_fn in initial_nodes:
        input_state = dict(state)
        start_time = time.time()

        if writer:
            writer({
                "event_type": "node_start",
                "task_id": task_id,
                "node": node_name,
                "title": title,
                "query": query,
            })

        output = node_fn(state)
        duration_ms = int((time.time() - start_time) * 1000)
        state.update(output)

        thinking = output.get("thinking", "")
        status = "done" if not output.get("error") else "error"

        event_data = {
            "event_type": "node_complete",
            "task_id": task_id,
            "node": node_name,
            "title": title,
            "status": status,
            "duration_ms": duration_ms,
        }

        if writer:
            writer(event_data)

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
            if writer:
                writer({
                    "event_type": "error",
                    "task_id": task_id,
                    "node": node_name,
                    "error": output.get("error"),
                })
            break

    # Conditional routing based on research need
    if state.get("error"):
        # Already errored out, return
        return state, trace

    needs_research = state.get("needs_external_research", True)

    if needs_research:
        # Full seller workflow
        seller_nodes = [
            ("execute_payment", "Execute Payment", "execute", execute_payment),
            ("send_research_request", "Send Research", "execute", send_research_request),
            ("fetch_result", "Fetch Result", "execute", fetch_result),
        ]
    else:
        # Direct answer workflow
        seller_nodes = [
            ("format_direct_answer", "Format Answer", "execute", format_direct_answer),
        ]

    # Execute conditional nodes
    for node_name, title, phase, node_fn in seller_nodes:
        input_state = dict(state)
        start_time = time.time()

        if writer:
            writer({
                "event_type": "node_start",
                "task_id": task_id,
                "node": node_name,
                "title": title,
                "query": query,
            })

        output = node_fn(state)
        duration_ms = int((time.time() - start_time) * 1000)
        state.update(output)

        thinking = output.get("thinking", "")
        status = "done" if not output.get("error") else "error"

        event_data = {
            "event_type": "node_complete",
            "task_id": task_id,
            "node": node_name,
            "title": title,
            "status": status,
            "duration_ms": duration_ms,
        }

        if node_name == "execute_payment" and not output.get("error"):
            payment_offer = output.get("payment_offer", {})
            event_data["payment_details"] = {
                "amount_usdc": payment_offer.get("amount_usdc", "0"),
                "seller_address": payment_offer.get("pay_to", ""),
            }

        if node_name == "send_research_request" and not output.get("error"):
            event_data["research_request_sent"] = {
                "seller_url": state.get("seller_url", ""),
                "query": query,
            }

        if node_name in ("fetch_result", "format_direct_answer") and not output.get("error"):
            result = output.get("result", {})
            event_data["research_result"] = {
                "title": result.get("title", ""),
                "summary": result.get("summary", "")[:200],
                "bullets_count": len(result.get("bullets", [])),
            }

        if writer:
            writer(event_data)

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
            if writer:
                writer({
                    "event_type": "error",
                    "task_id": task_id,
                    "node": node_name,
                    "error": output.get("error"),
                })
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
