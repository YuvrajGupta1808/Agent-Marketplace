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
    return json.loads(cleaned)




def _live_research(state: SellerState) -> tuple[str, list[str]]:
    """Generate research using LLM - no stubs or fallbacks."""
    settings = get_settings()
    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    context = ""
    if state.get("retrieval_context"):
        context = "\n".join(f"- {item['title']}: {item['snippet']}" for item in state["retrieval_context"])

    context_section = f"**Retrieved Context:**\n{context}\n\n" if context else ""

    completion = client.chat.completions.create(
        model=settings.seller_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a specialized research agent that conducts thorough analysis and generates evidence-based answers. "
                    "Think deeply about the query, analyze available context, and provide original insights. "
                    "Return ONLY valid JSON with keys 'summary' and 'bullets'. "
                    "'summary' must be 2-3 paragraphs of detailed, analytical findings. "
                    "'bullets' must be an array of 5-6 important, specific facts or insights derived from your analysis."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{context_section}"
                    f"**Research Query:** {state['query']}\n\n"
                    "Provide a comprehensive, well-reasoned analysis. Each point should be specific and evidence-based."
                ),
            },
        ],
        max_tokens=512,
        temperature=0.6,
    )

    response_text = completion.choices[0].message.content or ""
    payload = _extract_json(response_text)
    summary = payload.get("summary") or payload.get("Summary")
    bullets = payload.get("bullets") or payload.get("Bullets") or []

    if not summary:
        raise ValueError(f"LLM response missing 'summary' field. Response: {response_text[:200]}")
    if not isinstance(bullets, list) or len(bullets) == 0:
        raise ValueError(f"LLM response has invalid 'bullets' field. Response: {response_text[:200]}")

    return summary, bullets


def run_research(state: SellerState) -> dict:
    """Generate research findings using LLM. No stubs, no mock data."""
    settings = get_settings()

    if not settings.live_llm_enabled:
        raise RuntimeError(
            "LLM research is required but not configured. "
            "Please set FEATHERLESS_API_KEY environment variable."
        )

    summary, bullets = _live_research(state)
    return {"draft_summary": summary, "bullets": bullets}
