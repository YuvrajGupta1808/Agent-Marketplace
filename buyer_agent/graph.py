from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from buyer_agent.nodes.discover import discover_seller
from buyer_agent.nodes.fetch_result import fetch_result
from buyer_agent.nodes.pay import execute_payment
from buyer_agent.state import BuyerState

builder = StateGraph(BuyerState)
builder.add_node("discover_seller", discover_seller)
builder.add_node("execute_payment", execute_payment)
builder.add_node("fetch_result", fetch_result)
builder.add_edge(START, "discover_seller")
builder.add_edge("discover_seller", "execute_payment")
builder.add_edge("execute_payment", "fetch_result")
builder.add_edge("fetch_result", END)

buyer_graph = builder.compile()
