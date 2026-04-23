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
                    "You are a strategic research planner. Return ONLY valid JSON.\n"
                    '{"reasoning": "brief strategy explanation", "research_steps": [{"step": "action", "why": "relevance"}]}'
                ),
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nBriefly plan a research strategy as JSON.",
            },
        ],
        max_tokens=256,
        temperature=0.3,
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
