from __future__ import annotations

import hashlib
from pathlib import Path

from shared.config import get_settings
from shared.envfile import upsert_env_values


def _mock_address(seed: str) -> str:
    return "0x" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:40]


def deploy_contracts() -> dict[str, str]:
    _ = get_settings()
    return {
        "AGENT_ESCROW_ADDRESS": _mock_address("agent-escrow"),
        "SPENDING_LIMITER_ADDRESS": _mock_address("spending-limiter"),
    }


def main() -> None:
    values = deploy_contracts()
    upsert_env_values(Path(".env"), values)
    for key, value in values.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
