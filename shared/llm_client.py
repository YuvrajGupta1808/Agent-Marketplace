from __future__ import annotations

from typing import Any

from openai import OpenAI

from shared.llm_providers import get_provider_api_key, resolve_buyer_llm_config


class BuyerLlmNotConfigured(RuntimeError):
    pass


def get_buyer_openai_client(config: dict[str, Any] | None = None) -> tuple[OpenAI, dict[str, str]]:
    resolved = resolve_buyer_llm_config(config)
    api_key = get_provider_api_key(resolved["provider"])
    if api_key is None or not api_key.get_secret_value().strip():
        raise BuyerLlmNotConfigured(f"{resolved['provider_name']} is missing {resolved['api_key_env']}.")

    return (
        OpenAI(
            api_key=api_key.get_secret_value(),
            base_url=resolved["base_url"],
        ),
        resolved,
    )
