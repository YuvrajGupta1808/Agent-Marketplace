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

    def try_parse(s: str) -> dict | None:
        """Try to parse JSON with error handling."""
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None

    # Try strategies in order
    # 1. Original (most common case)
    result = try_parse(cleaned)
    if result:
        return result

    # 2. Remove trailing commas
    result = try_parse(_re.sub(r',(\s*[}\]])', r'\1', cleaned))
    if result:
        return result

    # 3. Balance braces (for incomplete JSON)
    balanced = cleaned.rstrip('}') + '}' * max(0, cleaned.count('{') - cleaned.count('}'))
    result = try_parse(balanced)
    if result:
        return result

    # 4. Try to extract just the first complete JSON object
    # Use a state machine to find matching braces
    depth = 0
    in_string = False
    escape = False
    start = -1

    for i, char in enumerate(cleaned):
        if escape:
            escape = False
            continue
        if char == '\\' and in_string:
            escape = True
            continue
        if char == '"' and (i == 0 or cleaned[i-1] != '\\'):
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    json_str = cleaned[start:i+1]
                    result = try_parse(json_str)
                    if result:
                        return result

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
