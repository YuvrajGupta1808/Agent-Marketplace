#!/usr/bin/env python
"""Test direct answer functionality for simple queries."""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

from buyer_agent.state import BuyerState
from buyer_agent.nodes.evaluate_need import evaluate_research_need
from buyer_agent.nodes.format_direct_answer import format_direct_answer

# Test 1: Greeting (should not need research)
print("Test 1: Greeting query")
print("=" * 60)
state: BuyerState = {
    "task_id": "test-1",
    "query": "Hi there, how are you?",
}
result = evaluate_research_need(state)
print(f"Needs external research: {result.get('needs_external_research')}")
print(f"Direct answer: {result.get('direct_answer')[:100] if result.get('direct_answer') else 'N/A'}")
print(f"Thinking: {result.get('thinking')}\n")

# Test 2: Definition (should not need research)
print("Test 2: Definition query")
print("=" * 60)
state = {
    "task_id": "test-2",
    "query": "What is photosynthesis?",
}
result = evaluate_research_need(state)
print(f"Needs external research: {result.get('needs_external_research')}")
print(f"Direct answer: {result.get('direct_answer')[:100] if result.get('direct_answer') else 'N/A'}")
print(f"Thinking: {result.get('thinking')}\n")

# Test 3: Current events (should need research)
print("Test 3: Current events query")
print("=" * 60)
state = {
    "task_id": "test-3",
    "query": "What are the latest news about cryptocurrency today?",
}
result = evaluate_research_need(state)
print(f"Needs external research: {result.get('needs_external_research')}")
print(f"Direct answer: {result.get('direct_answer')[:100] if result.get('direct_answer') else 'N/A'}")
print(f"Thinking: {result.get('thinking')}\n")

# Test 4: Format direct answer
print("Test 4: Format direct answer")
print("=" * 60)
state = {
    "task_id": "test-4",
    "query": "What is Arc?",
    "direct_answer": "Arc is an Ethereum test network launched by Protocol Labs. It's designed for testing smart contracts and blockchain applications before deploying to mainnet.",
}
result = format_direct_answer(state)
print(f"Formatted result: {result.get('result', {}).get('title')}")
print(f"Summary: {result.get('result', {}).get('summary')[:100]}")
