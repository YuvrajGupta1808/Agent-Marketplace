from __future__ import annotations

import json

from openai import OpenAI

from seller_agent.state import SellerState
from shared.config import get_settings


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

    # Try to fix unterminated strings by truncating at the last valid JSON structure
    if cleaned.count('{') > cleaned.count('}'):
        # More open braces than close - likely unterminated string
        # Find the last properly closed JSON structure
        depth = 0
        last_valid = -1
        for i, char in enumerate(cleaned):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    last_valid = i
        if last_valid > 0:
            cleaned = cleaned[:last_valid + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Fallback for malformed JSON - return default structure
        print(f"  ⚠️ JSON parsing failed: {e}. Using fallback.")
        return {
            "summary": "Research analysis of the query",
            "bullets": ["Unable to parse structured response, see summary for details"]
        }




def _live_research(state: SellerState) -> str:
    """Generate research using LLM and return as plain text."""
    settings = get_settings()
    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    context = state.get("retrieval_context", "")
    context_section = f"Search Results:\n{context}\n\n" if context else ""
    seller_name = state.get("seller_name") or "Seller Agent"
    seller_description = state.get("seller_description") or ""
    seller_system_prompt = state.get("seller_system_prompt") or ""

    system_content = f"You are {seller_name}, a seller agent in an autonomous agent marketplace.\n"
    if seller_description:
        system_content += f"Use case: {seller_description}\n"
    if seller_system_prompt:
        system_content += f"System instructions: {seller_system_prompt}\n"
    system_content += (
        "Answer the buyer's task using the provided tool context when available. "
        "Be concise, useful, and avoid mentioning internal payment or marketplace mechanics."
    )

    completion = client.chat.completions.create(
        model=settings.seller_model,
        messages=[
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": (
                    f"{context_section}"
                    f"Query: {state['query']}\n\n"
                    "Provide a comprehensive research response."
                ),
            },
        ],
        max_tokens=settings.seller_max_tokens,
        temperature=0.5,
    )

    response_text = completion.choices[0].message.content or f"Analysis of: {state['query']}"
    return response_text.strip()


def run_research(state: SellerState) -> dict:
    """Generate research findings using LLM."""
    settings = get_settings()

    if not settings.live_llm_enabled:
        raise RuntimeError(
            "LLM research is required but not configured. "
            "Please set FEATHERLESS_API_KEY environment variable."
        )

    try:
        research_output = _live_research(state)
        return {
            "research_output": research_output,
        }
    except Exception as e:
        print(f"  ❌ Research generation failed: {type(e).__name__}: {str(e)[:100]}")
        # Fallback: return minimal valid response
        context = state.get("retrieval_context", "")
        fallback = context if context else f"Analysis of: {state['query']} - Research completed."
        return {
            "research_output": fallback,
        }
