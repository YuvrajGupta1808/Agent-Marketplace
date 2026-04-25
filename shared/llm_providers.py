from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import SecretStr

from shared.config import Settings, get_settings


ProviderId = str


@dataclass(frozen=True)
class LlmModelOption:
    id: str
    name: str
    tier: str
    payment_floor_usdc: str
    description: str


@dataclass(frozen=True)
class LlmProvider:
    id: ProviderId
    name: str
    base_url: str
    api_key_env: str
    docs_url: str
    model_source_url: str
    models: tuple[LlmModelOption, ...]


PAYMENT_FLOORS = {
    "small": "0.200000",
    "medium": "0.750000",
    "large": "1.500000",
}


LLM_PROVIDERS: tuple[LlmProvider, ...] = (
    LlmProvider(
        id="aimlapi",
        name="AI/ML API",
        base_url="https://api.aimlapi.com/v1",
        api_key_env="AIML_API_KEY",
        docs_url="https://docs.aimlapi.com/",
        model_source_url="https://docs.aimlapi.com/",
        models=(
            LlmModelOption(
                id="gpt-4o-mini",
                name="GPT-4o Mini",
                tier="small",
                payment_floor_usdc=PAYMENT_FLOORS["small"],
                description="Small chat model for buyer routing and planning.",
            ),
            LlmModelOption(
                id="gpt-4o-mini-2024-07-18",
                name="GPT-4o Mini (2024-07-18)",
                tier="medium",
                payment_floor_usdc=PAYMENT_FLOORS["medium"],
                description="Pinned GPT-4o mini revision for deterministic behavior.",
            ),
            LlmModelOption(
                id="openai/gpt-4o",
                name="OpenAI GPT-4o",
                tier="large",
                payment_floor_usdc=PAYMENT_FLOORS["large"],
                description="Larger model for higher quality buyer synthesis.",
            ),
            LlmModelOption(
                id="openai/gpt-4.1-mini-2025-04-14",
                name="OpenAI GPT-4.1 Mini",
                tier="medium",
                payment_floor_usdc=PAYMENT_FLOORS["medium"],
                description="Balanced GPT-4.1 class model for stronger planning.",
            ),
            LlmModelOption(
                id="openai/o4-mini-2025-04-16",
                name="OpenAI o4 Mini",
                tier="large",
                payment_floor_usdc=PAYMENT_FLOORS["large"],
                description="Reasoning-first OpenAI model routed through AI/ML API.",
            ),
            LlmModelOption(
                id="google/gemini-2.5-flash",
                name="Gemini 2.5 Flash (via AI/ML)",
                tier="medium",
                payment_floor_usdc=PAYMENT_FLOORS["medium"],
                description="Google Gemini model available on AI/ML OpenAI-compatible route.",
            ),
            LlmModelOption(
                id="claude-sonnet-4-6",
                name="Claude Sonnet 4.6 (via AI/ML)",
                tier="large",
                payment_floor_usdc=PAYMENT_FLOORS["large"],
                description="Anthropic model accessed through AI/ML aggregation.",
            ),
        ),
    ),
    LlmProvider(
        id="featherless",
        name="Featherless",
        base_url="https://api.featherless.ai/v1",
        api_key_env="FEATHERLESS_API_KEY",
        docs_url="https://featherless.ai/docs/api-overview-and-common-options",
        model_source_url="https://featherless.ai/models?v=c",
        models=(
            LlmModelOption(
                id="Qwen/Qwen3-4B-Instruct-2507",
                name="Qwen3 4B Instruct",
                tier="small",
                payment_floor_usdc=PAYMENT_FLOORS["small"],
                description="Compact open model for buyer planning.",
            ),
            LlmModelOption(
                id="Qwen/Qwen3-8B",
                name="Qwen3 8B",
                tier="small",
                payment_floor_usdc=PAYMENT_FLOORS["small"],
                description="Small-to-medium open model for low-latency buyer execution.",
            ),
            LlmModelOption(
                id="Qwen/Qwen3-14B",
                name="Qwen3 14B",
                tier="medium",
                payment_floor_usdc=PAYMENT_FLOORS["medium"],
                description="Balanced open model for better planning depth.",
            ),
            LlmModelOption(
                id="meta-llama/Llama-3.1-8B-Instruct",
                name="Llama 3.1 8B Instruct",
                tier="medium",
                payment_floor_usdc=PAYMENT_FLOORS["medium"],
                description="General buyer planning and synthesis model.",
            ),
            LlmModelOption(
                id="meta-llama/Llama-3.3-70B-Instruct",
                name="Llama 3.3 70B Instruct",
                tier="large",
                payment_floor_usdc=PAYMENT_FLOORS["large"],
                description="Large open model for deeper buyer reasoning tasks.",
            ),
            LlmModelOption(
                id="deepseek-ai/DeepSeek-V3.2",
                name="DeepSeek V3.2",
                tier="large",
                payment_floor_usdc=PAYMENT_FLOORS["large"],
                description="Large model for complex buyer reasoning.",
            ),
            LlmModelOption(
                id="mistralai/Mistral-7B-Instruct-v0.3",
                name="Mistral 7B Instruct v0.3",
                tier="small",
                payment_floor_usdc=PAYMENT_FLOORS["small"],
                description="Compact instruct model for economical buyer planning.",
            ),
        ),
    ),
    LlmProvider(
        id="gemini",
        name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        docs_url="https://ai.google.dev/gemini-api/docs/openai",
        model_source_url="https://ai.google.dev/gemini-api/docs/models",
        models=(
            LlmModelOption(
                id="gemini-2.5-flash-lite",
                name="Gemini 2.5 Flash-Lite",
                tier="small",
                payment_floor_usdc=PAYMENT_FLOORS["small"],
                description="Low-cost Gemini model for lightweight buyer planning.",
            ),
            LlmModelOption(
                id="gemini-2.5-flash",
                name="Gemini 2.5 Flash",
                tier="medium",
                payment_floor_usdc=PAYMENT_FLOORS["medium"],
                description="Balanced Gemini model for buyer workflows.",
            ),
            LlmModelOption(
                id="gemini-2.5-pro",
                name="Gemini 2.5 Pro",
                tier="large",
                payment_floor_usdc=PAYMENT_FLOORS["large"],
                description="Higher-capability Gemini model for complex workflows.",
            ),
            LlmModelOption(
                id="gemini-3-flash-preview",
                name="Gemini 3 Flash Preview",
                tier="large",
                payment_floor_usdc=PAYMENT_FLOORS["large"],
                description="Frontier Gemini model for richer buyer reasoning.",
            ),
        ),
    ),
)


def _secret_is_set(value: SecretStr | None) -> bool:
    if value is None:
        return False
    return bool(value.get_secret_value().strip())


def _provider_secret(settings: Settings, provider_id: ProviderId) -> SecretStr | None:
    if provider_id == "aimlapi":
        return settings.aiml_api_key or settings.aimlapi_api_key
    if provider_id == "featherless":
        return settings.featherless_api_key
    if provider_id == "gemini":
        return settings.gemini_api_key
    return None


def get_provider(provider_id: ProviderId | None) -> LlmProvider:
    normalized = (provider_id or "featherless").strip().lower()
    for provider in LLM_PROVIDERS:
        if provider.id == normalized:
            return provider
    return get_provider("featherless")


def get_model(provider: LlmProvider, model_id: str | None) -> LlmModelOption:
    if model_id:
        for model in provider.models:
            if model.id == model_id:
                return model
    return provider.models[0]


def resolve_buyer_llm_config(config: dict[str, Any] | None = None) -> dict[str, str]:
    requested = config or {}
    provider = get_provider(str(requested.get("provider") or ""))
    model = get_model(provider, str(requested.get("model") or ""))
    return {
        "provider": provider.id,
        "provider_name": provider.name,
        "base_url": provider.base_url,
        "api_key_env": provider.api_key_env,
        "model": model.id,
        "model_name": model.name,
        "tier": model.tier,
        "payment_floor_usdc": model.payment_floor_usdc,
    }


def get_provider_api_key(provider_id: ProviderId) -> SecretStr | None:
    return _provider_secret(get_settings(), provider_id)


def buyer_llm_enabled(config: dict[str, Any] | None = None) -> bool:
    resolved = resolve_buyer_llm_config(config)
    return _secret_is_set(get_provider_api_key(resolved["provider"]))


def list_provider_payloads() -> list[dict[str, Any]]:
    settings = get_settings()
    payloads: list[dict[str, Any]] = []
    for provider in LLM_PROVIDERS:
        enabled = _secret_is_set(_provider_secret(settings, provider.id))
        payloads.append(
            {
                "id": provider.id,
                "name": provider.name,
                "base_url": provider.base_url,
                "api_key_env": provider.api_key_env,
                "docs_url": provider.docs_url,
                "model_source_url": provider.model_source_url,
                "enabled": enabled,
                "disabled_reason": None if enabled else f"Missing {provider.api_key_env}",
                "models": [
                    {
                        "id": model.id,
                        "name": model.name,
                        "tier": model.tier,
                        "payment_floor_usdc": model.payment_floor_usdc,
                        "description": model.description,
                    }
                    for model in provider.models
                ],
            }
        )
    return payloads


def coerce_payment_limit(value: Any, fallback: str) -> str:
    floor = Decimal(fallback)
    try:
        amount = Decimal(str(value))
    except Exception:
        amount = floor
    if amount < floor:
        amount = floor
    return f"{amount.quantize(Decimal('0.000001'))}"
