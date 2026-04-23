from __future__ import annotations

import json
import re

from openai import OpenAI

from buyer_agent.state import BuyerState
from shared.config import get_settings


def _extract_json(content: str) -> dict:
    """Robustly extract JSON from LLM response."""
    import re as _re

    cleaned = content.strip()

    # Strip thinking blocks
    cleaned = _re.sub(r"<think>.*?</think>", "", cleaned, flags=_re.DOTALL).strip()

    # Remove markdown code blocks
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = next((part for part in parts if "{" in part), cleaned)
        cleaned = cleaned.replace("json", "", 1).strip()

    # Find JSON object
    match = _re.search(r"\{.*\}", cleaned, flags=_re.DOTALL)
    if match:
        cleaned = match.group(0)

    # Try to parse with error recovery
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Remove trailing commas
        cleaned = _re.sub(r',(\s*[}\]])', r'\1', cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse JSON. Original: {content[:300]}...")


def _generate_research_plan_llm(query: str) -> dict:
    """Generate research plan using LLM. No fallbacks, no stubs."""
    settings = get_settings()

    if not settings.live_llm_enabled:
        raise RuntimeError(
            "LLM-based planning is required but not configured. "
            "Please set FEATHERLESS_API_KEY environment variable."
        )

    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    completion = client.chat.completions.create(
        model=settings.orchestrator_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strategic research planner for an autonomous buyer agent. "
                    "Analyze queries deeply and create a detailed, thoughtful research strategy. "
                    "Your reasoning should explain WHY this approach is best.\n\n"
                    "Return ONLY a JSON object with:\n"
                    '{\n'
                    '  "reasoning": "detailed explanation of your research strategy and why it works",\n'
                    '  "research_steps": [\n'
                    '    {"step": "specific action or focus area", "why": "importance to answering the query"},\n'
                    '    ...\n'
                    '  ]\n'
                    '}'
                ),
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nDevelop a comprehensive research strategy for this query. Think about what information is needed, what angles to explore, and why.",
            },
        ],
        max_tokens=384,
        temperature=0.6,
    )

    content = completion.choices[0].message.content or ""
    if not content:
        raise ValueError("LLM returned empty response for research planning")

    plan_data = _extract_json(content)

    if not plan_data.get("reasoning"):
        raise ValueError(f"LLM response missing 'reasoning' field. Response: {content[:200]}")

    return plan_data


def plan_research_steps(state: BuyerState) -> dict:
    """Generate LLM-powered research plan with detailed reasoning (ReAct: Reason step)."""
    query = state["query"].strip()

    plan_data = _generate_research_plan_llm(query)
    reasoning = plan_data.get("reasoning")
    research_steps = plan_data.get("research_steps", [])

    if not reasoning:
        raise ValueError(f"LLM failed to generate reasoning for query: {query}")

    execution_plan = [
        f"1. Discover the seller endpoint for task `{state['task_id']}`.",
        f"2. Prepare the research request for query: {query}",
        "3. Execute payment authorization and settlement.",
        "4. Send the paid research request to the seller.",
        "5. Fetch and normalize the final research result.",
    ]

    return {
        "reasoning": reasoning,
        "research_plan": research_steps,
        "execution_plan": execution_plan,
    }
