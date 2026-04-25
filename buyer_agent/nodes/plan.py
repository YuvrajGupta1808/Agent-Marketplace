from __future__ import annotations

import json
import re

from openai import OpenAI

from buyer_agent.state import BuyerState
from buyer_agent.utils import extract_json
from shared.config import get_settings


def _extract_json_deprecated(content: str) -> dict:
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


def _generate_research_plan_llm(query: str, agent_context: str = "") -> dict:
    """Generate research plan using LLM."""
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

    system_content = "You are a strategic research planner. Return ONLY valid JSON.\n"
    if agent_context:
        system_content = f"{agent_context}\n\nAs this agent, plan a targeted research strategy. Return ONLY valid JSON.\n"
    system_content += '{"research_steps": [{"step": "action", "why": "relevance"}]}'

    completion = client.chat.completions.create(
        model=settings.orchestrator_model,
        messages=[
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nPlan a research strategy as JSON.",
            },
        ],
        max_tokens=256,
        temperature=0.3,
    )

    content = completion.choices[0].message.content or ""
    if not content:
        raise ValueError("LLM returned empty response for research planning")

    try:
        plan_data = extract_json(content)
    except ValueError:
        # Fallback: if JSON parsing fails, create a default plan
        plan_data = {
            "research_steps": [
                {"step": "Research the query comprehensively", "why": "To answer the user's question"}
            ]
        }

    plan_data["thinking"] = ""
    return plan_data


def plan_research_steps(state: BuyerState) -> dict:
    """Generate LLM-powered research plan using actual thinking model."""
    query = state["query"].strip()
    print(f"  📝 plan_research_steps: '{query[:50]}'")

    # Build agent context from identity fields
    agent_context = ""
    agent_name = state.get("buyer_agent_name", "")
    agent_description = state.get("buyer_agent_description", "")
    agent_system_prompt = state.get("buyer_agent_system_prompt", "")

    if agent_system_prompt:
        agent_context = agent_system_prompt
    elif agent_description:
        agent_context = f"You are {agent_name}: {agent_description}." if agent_name else agent_description
    elif agent_name:
        agent_context = f"You are {agent_name}."

    plan_data = _generate_research_plan_llm(query, agent_context=agent_context)
    thinking = plan_data.get("thinking", "")
    research_steps = plan_data.get("research_steps", [])
    print(f"    ✓ Generated {len(research_steps)} research step(s)")

    execution_plan = [
        f"1. Discover the seller endpoint for task `{state['task_id']}`.",
        f"2. Prepare the research request for query: {query}",
        "3. Execute payment authorization and settlement.",
        "4. Send the paid research request to the seller.",
        "5. Fetch and normalize the final research result.",
    ]

    return {
        "thinking": thinking,
        "research_plan": research_steps,
        "execution_plan": execution_plan,
    }
