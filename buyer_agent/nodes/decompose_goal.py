from __future__ import annotations

import uuid

from openai import OpenAI

from buyer_agent.state import BuyerState
from buyer_agent.utils import extract_json
from shared.config import get_settings


def decompose_goal(state: BuyerState) -> dict:
    """
    Decompose user goal into as many specific tasks as needed, informed by buyer agent's identity.

    Task count is dynamic based on goal complexity:
    - Simple goals: 1-2 tasks
    - Moderate goals: 2-4 tasks
    - Complex goals: 4+ tasks
    """
    user_goal = state.get("user_goal", "").strip()
    query = state.get("query", user_goal).strip()
    agent_name = state.get("buyer_agent_name", "Buyer Agent")
    agent_description = state.get("buyer_agent_description", "")

    print(f"  📋 decompose_goal: '{query[:50]}'")

    settings = get_settings()
    if not settings.live_llm_enabled:
        raise RuntimeError(
            "LLM-based goal decomposition is required but not configured. "
            "Please set FEATHERLESS_API_KEY environment variable."
        )

    system_message = f"You are {agent_name}"
    if agent_description:
        system_message += f": {agent_description}"
    system_message += ".\n\n"
    system_message += """Break down the user's goal into concrete, specific tasks that can be independently researched or executed.

Sizing:
- Simple goals: 1-2 tasks
- Moderate goals: 2-4 tasks
- Complex goals: 4-7+ tasks (as many as needed)

Each task should:
- Be a specific query or action (not a vague directive)
- Be completable by a research/specialist seller agent
- Together cover the full user goal comprehensively

Return ONLY valid JSON:
{
    "tasks": [
        {"task_id": "task-1", "query": "specific query", "objective": "what this answers"},
        ...
    ]
}"""

    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    try:
        completion = client.chat.completions.create(
            model=settings.orchestrator_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Goal: {query}\n\nDecompose this into tasks."},
            ],
            max_tokens=512,
            temperature=0.3,
        )

        content = completion.choices[0].message.content or ""
        if not content:
            raise ValueError("LLM returned empty response for goal decomposition")

        try:
            result = extract_json(content)
        except ValueError:
            # Fallback: create a single task from the goal
            task_id = str(uuid.uuid4())[:8]
            result = {
                "tasks": [
                    {
                        "task_id": f"task-{task_id}",
                        "query": query,
                        "objective": "Research and provide a comprehensive answer to the goal",
                    }
                ]
            }

        tasks = result.get("tasks", [])

        # Ensure task_id is set for each task
        for i, task in enumerate(tasks):
            if not task.get("task_id"):
                task["task_id"] = f"task-{i+1}"

        print(f"    ✓ Decomposed into {len(tasks)} task(s)")
        return {"tasks": tasks, "thinking": ""}

    except Exception as e:
        print(f"    ⚠️ Decomposition error: {e}")
        # Fallback: create a single task from the goal
        task_id = str(uuid.uuid4())[:8]
        return {
            "tasks": [
                {
                    "task_id": f"task-{task_id}",
                    "query": query,
                    "objective": "Research and provide a comprehensive answer",
                }
            ],
            "thinking": f"Decomposition error: {str(e)}",
        }
