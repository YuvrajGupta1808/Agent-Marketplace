from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    seller_host: str = "127.0.0.1"
    seller_port: int = 8001
    seller_research_path: str = "/research"
    database_path: str = "data/marketplace.db"

    arc_chain_id: int = 5_042_002
    arc_blockchain: str = "ARC-TESTNET"
    arc_rpc_url: str = "https://rpc.testnet.arc.network"
    arc_explorer_url: str = "https://testnet.arcscan.app"
    arc_usdc_contract: str = "0x3600000000000000000000000000000000000000"

    planner_mode: Literal["heuristic", "live"] = "heuristic"
    research_mode: Literal["stub", "live"] = "stub"
    seller_price_usdc: float = 0.01
    request_timeout_seconds: float = 90.0

    featherless_api_key: SecretStr | None = None
    featherless_base_url: str = "https://api.featherless.ai/v1"
    aiml_api_key: SecretStr | None = None
    aimlapi_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    orchestrator_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    seller_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    thinking_model: str = "Qwen/QwQ-32B-Preview"
    seller_max_tokens: int = 1400
    synthesizer_max_tokens: int = 1600

    tavily_api_key: SecretStr | None = None
    yutori_api_key: SecretStr | None = None
    yutori_poll_timeout_seconds: float = 25.0
    yutori_poll_interval_seconds: float = 2.0
    mediastack_api_key: SecretStr | None = None
    newsapi_api_key: SecretStr | None = None

    circle_api_key: SecretStr | None = None
    circle_entity_secret: SecretStr | None = None
    circle_wallet_set_id: str | None = None
    circle_account_type: Literal["EOA", "SCA"] = "EOA"
    circle_fee_level: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"

    agent_escrow_address: str | None = None
    spending_limiter_address: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def seller_base_url(self) -> str:
        return f"http://{self.seller_host}:{self.seller_port}"

    @property
    def api_base_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def circle_enabled(self) -> bool:
        return bool(self.circle_api_key and self.circle_entity_secret)

    @property
    def live_llm_enabled(self) -> bool:
        return bool(self.featherless_api_key)

    @property
    def database_file(self) -> Path:
        return Path(self.database_path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
