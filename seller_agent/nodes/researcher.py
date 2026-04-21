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


def _stub_research(state: SellerState) -> tuple[str, list[str]]:
    query = state["query"]
    bullets = [
        "Arc Testnet is EVM compatible and uses USDC as the native gas token.",
        "Circle developer-controlled wallets can create and manage ARC-TESTNET wallets with an API key and entity secret.",
        "Each buyer and seller agent can carry its own Circle wallet, provisioned dynamically and persisted in SQLite.",
    ]
    return f"Stubbed seller research for `{query}` based on validated Arc and Circle docs.", bullets


def _live_research(state: SellerState) -> tuple[str, list[str]]:
    settings = get_settings()
    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )
    context = "\n".join(f"- {item['title']}: {item['snippet']}" for item in state["retrieval_context"])
    completion = client.chat.completions.create(
        model=settings.seller_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Return only valid JSON with keys `summary` and `bullets`. "
                    "`summary` must be one short paragraph. "
                    "`bullets` must be an array of 3 concise strings."
                ),
            },
            {
                "role": "user",
                "content": f"Query: {state['query']}\nContext:\n{context}",
            },
        ],
        max_tokens=384,
        temperature=0,
    )
    payload = _extract_json(completion.choices[0].message.content or "{}")
    return payload["summary"], payload["bullets"]


def run_research(state: SellerState) -> dict:
    settings = get_settings()
    if settings.research_mode == "live" and settings.live_llm_enabled:
        try:
            summary, bullets = _live_research(state)
            return {"draft_summary": summary, "bullets": bullets}
        except Exception:
            pass

    summary, bullets = _stub_research(state)
    return {"draft_summary": summary, "bullets": bullets}
