from __future__ import annotations

import json
import re

from openai import OpenAI
from langgraph.config import get_stream_writer

from orchestrator.prompts import PLANNER_SYSTEM_PROMPT
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
    result = try_parse(cleaned)
    if result:
        return result

    result = try_parse(_re.sub(r',(\s*[}\]])', r'\1', cleaned))
    if result:
        return result

    balanced = cleaned.rstrip('}') + '}' * max(0, cleaned.count('{') - cleaned.count('}'))
    result = try_parse(balanced)
    if result:
        return result

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


def plan_tasks(state: OrchestratorState) -> dict:
    """Plan research tasks from user goal."""
    goal = state["user_goal"].strip()
    print(f"\n📋 plan_tasks: Goal = '{goal}'")

    try:
        writer = get_stream_writer()
    except (RuntimeError, AttributeError):
        writer = None

    if state.get("clarification_answer"):
        goal = f"{goal}\nClarification: {state['clarification_answer']}"

    settings = get_settings()
    if not settings.live_llm_enabled:
        raise RuntimeError(
            "LLM-based planning is required but not configured. "
            "Please set FEATHERLESS_API_KEY environment variable."
        )

    if writer:
        writer({
            "event_type": "planning",
            "message": f"Analyzing goal and planning tasks...",
        })

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

    try:
        payload = _extract_json(content)
    except ValueError as e:
        print(f"  ⚠️ JSON parsing failed: {e}")
        payload = {"tasks": [{"task_id": "task-1", "query": goal, "objective": "Research the user goal"}]}

    task_specs = [TaskSpec.model_validate(task) for task in payload.get("tasks", [])]
    print(f"  ✓ Generated {len(task_specs)} task(s)")
    for spec in task_specs:
        print(f"    - {spec.query[:60]}")

    if writer:
        try:
            writer({
                "event_type": "tasks_planned",
                "task_count": len(task_specs),
                "tasks": [{"task_id": spec.task_id, "query": spec.query} for spec in task_specs[:5]],
            })
        except Exception as e:
            print(f"  ⚠️ Writer error: {e}")

    return {
        "task_specs": task_specs,
        "pending_question": None,
    }
