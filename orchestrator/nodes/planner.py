from __future__ import annotations

import json
import re

from openai import OpenAI

from orchestrator.prompts import PLANNER_SYSTEM_PROMPT
from orchestrator.state import OrchestratorState
from shared.config import get_settings
from shared.types import TaskSpec


def _extract_json(content: str) -> dict:
    import re as _re
    cleaned = content.strip()
    # Strip <think>...</think> blocks (Qwen3 and other thinking models)
    cleaned = _re.sub(r"<think>.*?</think>", "", cleaned, flags=_re.DOTALL).strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = next((part for part in parts if "{" in part), cleaned)
        cleaned = cleaned.replace("json", "", 1).strip()
    # Find the first {...} block if the model included surrounding text
    match = _re.search(r"\{.*\}", cleaned, flags=_re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def _heuristic_plan(goal: str) -> list[TaskSpec]:
    requested_count = 1
    match = re.search(r"\btop\s+(\d+)\b", goal, flags=re.IGNORECASE)
    if match:
        requested_count = max(1, min(3, int(match.group(1))))

    fragments = [part.strip() for part in re.split(r"[;\n]+", goal) if part.strip()]
    if len(fragments) > 1:
        return [
            TaskSpec(task_id=f"task-{index}", query=fragment)
            for index, fragment in enumerate(fragments, start=1)
        ]

    if requested_count == 1:
        return [TaskSpec(task_id="task-1", query=goal)]

    return [
        TaskSpec(task_id=f"task-{index}", query=f"{goal} (item {index})")
        for index in range(1, requested_count + 1)
    ]


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
            {
                "role": "user",
                "content": (
                    "Return only compact JSON with a `tasks` array. "
                    "Each task needs `task_id`, `query`, and `objective`. "
                    "Do not include commentary or markdown fences.\n"
                    f"Goal: {goal}"
                ),
            },
        ],
        max_tokens=256,
        temperature=0,
    )
    content = completion.choices[0].message.content or "{}"
    payload = _extract_json(content)
    return [TaskSpec.model_validate(task) for task in payload.get("tasks", [])]


def plan_tasks(state: OrchestratorState) -> dict:
    goal = state["user_goal"].strip()
    if len(goal) < 6 and not state.get("clarification_answer"):
        return {"pending_question": "What should the marketplace research for you?"}

    if state.get("clarification_answer"):
        goal = f"{goal}\nClarification: {state['clarification_answer']}"

    settings = get_settings()
    if settings.planner_mode == "live" and settings.live_llm_enabled:
        try:
            task_specs = _live_plan(goal)
            if not task_specs:
                task_specs = _heuristic_plan(goal)
        except Exception:
            task_specs = _heuristic_plan(goal)
    else:
        task_specs = _heuristic_plan(goal)
    return {
        "task_specs": task_specs,
        "pending_question": None,
    }
