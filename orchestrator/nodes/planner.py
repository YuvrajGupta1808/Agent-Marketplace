from __future__ import annotations

import json
import re

from openai import OpenAI

from orchestrator.prompts import INTENT_DETECTION_PROMPT, PLANNER_SYSTEM_PROMPT
from orchestrator.state import OrchestratorState
from shared.config import get_settings
from shared.types import TaskSpec


def _extract_json(content: str) -> dict:
    """Robustly extract JSON from LLM response, handling common formatting issues."""
    import re as _re

    cleaned = content.strip()

    # Strip thinking blocks
    cleaned = _re.sub(r"<think>.*?</think>", "", cleaned, flags=_re.DOTALL).strip()

    # Remove markdown code blocks
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = next((part for part in parts if "{" in part), cleaned)
        cleaned = cleaned.replace("json", "", 1).strip()

    # Try multiple recovery strategies
    strategies = [
        lambda s: s,  # Original
        lambda s: _re.sub(r',(\s*[}\]])', r'\1', s),  # Remove trailing commas
        lambda s: _re.sub(r':\s*"([^"]*?),', r': "\1",', s),  # Fix broken string values
        lambda s: s.rstrip('}') + '}' * (s.count('{') - s.count('}')),  # Balance braces
    ]

    for strategy in strategies:
        try:
            # Find JSON object - be greedy to handle incomplete JSON
            match = _re.search(r'\{.*?\}(?:\s*(?:,\s*\{.*?\})*)?', strategy(cleaned), flags=_re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                json_str = strategy(cleaned)

            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            continue

    raise ValueError(f"Failed to parse JSON after all recovery attempts. Original: {content[:300]}...")


def _detect_intent(goal: str) -> dict:
    """Detect query intent using LLM. Handles conversational, factual, and research queries."""
    settings = get_settings()

    if not settings.live_llm_enabled:
        raise RuntimeError(
            "LLM-based intent detection is required but not configured. "
            "Please set FEATHERLESS_API_KEY environment variable."
        )

    # Simple heuristic for very short/greeting queries
    goal_lower = goal.lower().strip()
    simple_greetings = {"hi", "hello", "hey", "greetings", "what's up", "howdy", "hola"}
    if goal_lower in simple_greetings or len(goal_lower) <= 3:
        return {
            "intent": "conversational",
            "reasoning": f"Simple greeting: '{goal}'",
            "direct_answer": f"Hello! I'm an autonomous research agent ready to help. How can I assist you today?",
        }

    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    completion = client.chat.completions.create(
        model=settings.orchestrator_model,
        messages=[
            {"role": "system", "content": INTENT_DETECTION_PROMPT},
            {"role": "user", "content": f"Analyze and classify this goal: {goal}"},
        ],
        max_tokens=256,
        temperature=0.2,
    )

    content = completion.choices[0].message.content or ""
    if not content:
        raise ValueError("LLM returned empty response for intent detection")

    try:
        result = _extract_json(content)
    except Exception as e:
        print(f"Warning: Intent detection JSON parsing failed: {e}. Treating as research query.")
        return {
            "intent": "research",
            "reasoning": "Could not parse intent, defaulting to research",
            "direct_answer": None,
        }

    if not result.get("intent"):
        raise ValueError(f"LLM response missing 'intent' field. Response: {content[:200]}")

    return result




def _live_plan(goal: str) -> list[TaskSpec]:
    settings = get_settings()
    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )
    completion = client.chat.completions.create(
        model=settings.orchestrator_model,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Goal: {goal}"},
        ],
        max_tokens=256,
        temperature=0,
    )
    content = completion.choices[0].message.content or "{}"
    payload = _extract_json(content)
    return [TaskSpec.model_validate(task) for task in payload.get("tasks", [])]


def plan_tasks(state: OrchestratorState) -> dict:
    goal = state["user_goal"].strip()

    if state.get("clarification_answer"):
        goal = f"{goal}\nClarification: {state['clarification_answer']}"

    # Detect query intent first - handles all queries including short greetings
    intent_result = _detect_intent(goal)
    query_intent = intent_result.get("intent", "research")
    is_conversational = query_intent == "conversational"
    direct_answer = intent_result.get("direct_answer")

    if is_conversational and direct_answer:
        return {
            "query_intent": query_intent,
            "is_conversational": True,
            "direct_answer": direct_answer,
            "task_specs": [],
            "pending_question": None,
        }

    # For research queries, use LLM-based planning (no heuristic fallback)
    settings = get_settings()
    if not settings.live_llm_enabled:
        raise RuntimeError(
            "LLM-based planning is required but not configured. "
            "Please set FEATHERLESS_API_KEY environment variable."
        )

    task_specs = _live_plan(goal)

    return {
        "query_intent": query_intent,
        "is_conversational": is_conversational,
        "direct_answer": direct_answer,
        "task_specs": task_specs,
        "pending_question": None,
    }
