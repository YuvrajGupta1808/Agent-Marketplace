from __future__ import annotations

import json
import re

from openai import OpenAI

from buyer_agent.state import BuyerState
from buyer_agent.utils import extract_json
from shared.config import get_settings


def _extract_json_deprecated(content: str) -> dict:
    """Robustly extract JSON from LLM response."""
    cleaned = content.strip()
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = next((part for part in parts if "{" in part), cleaned)
        cleaned = cleaned.replace("json", "", 1).strip()

    def try_parse(s: str) -> dict | None:
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None

    result = try_parse(cleaned)
    if result:
        return result

    result = try_parse(re.sub(r',(\s*[}\]])', r'\1', cleaned))
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


def evaluate_research_need(state: BuyerState) -> dict:
    """Evaluate if query needs external research. If not, generate direct answer."""
    query = state["query"].strip()
    print(f"  🔍 evaluate_research_need: '{query[:50]}'")

    settings = get_settings()
    if not settings.live_llm_enabled:
        # If LLM not available, assume research is needed
        return {
            "needs_external_research": True,
            "direct_answer": None,
            "thinking": "LLM not available, proceeding with seller research",
        }

    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    evaluation_prompt = f"""Analyze this query: "{query}"

Determine if this query:
1. Can be answered directly with general knowledge (greetings, definitions, basic facts)
2. Requires external research (current events, real-time data, specific URLs, analysis of novel information)

If it can be answered directly, provide a helpful answer.

Return JSON:
{{
    "needs_external_research": boolean,
    "answer": "Your direct answer if needs_external_research is false, else null",
    "reasoning": "Brief explanation of why"
}}"""

    try:
        completion = client.chat.completions.create(
            model=settings.orchestrator_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Return ONLY valid JSON.",
                },
                {
                    "role": "user",
                    "content": evaluation_prompt,
                },
            ],
            max_tokens=512,
            temperature=0.3,
        )

        content = completion.choices[0].message.content or ""
        if not content:
            return {
                "needs_external_research": True,
                "direct_answer": None,
                "thinking": "LLM returned empty response, proceeding with seller research",
            }

        try:
            result = extract_json(content)
        except ValueError:
            return {
                "needs_external_research": True,
                "direct_answer": None,
                "thinking": "Failed to parse LLM response, proceeding with seller research",
            }

        needs_research = result.get("needs_external_research", True)
        answer = result.get("answer") if not needs_research else None
        reasoning = result.get("reasoning", "")

        if needs_research:
            print(f"    ✓ Needs external research: {reasoning}")
            return {
                "needs_external_research": True,
                "direct_answer": None,
                "thinking": reasoning,
            }
        else:
            print(f"    ✓ Can answer directly: {reasoning}")
            return {
                "needs_external_research": False,
                "direct_answer": answer or "",
                "thinking": reasoning,
            }

    except Exception as e:
        print(f"    ⚠️ Evaluation error: {e}, proceeding with seller research")
        return {
            "needs_external_research": True,
            "direct_answer": None,
            "thinking": f"Evaluation error: {str(e)}",
        }
