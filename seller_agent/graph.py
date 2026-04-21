from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from seller_agent.nodes.formatter import format_response
from seller_agent.nodes.researcher import run_research
from seller_agent.nodes.retriever import retrieve_context
from seller_agent.state import SellerState

builder = StateGraph(SellerState)
builder.add_node("retrieve_context", retrieve_context)
builder.add_node("run_research", run_research)
builder.add_node("format_response", format_response)
builder.add_edge(START, "retrieve_context")
builder.add_edge("retrieve_context", "run_research")
builder.add_edge("run_research", "format_response")
builder.add_edge("format_response", END)

seller_graph = builder.compile()
