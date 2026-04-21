from __future__ import annotations

from pathlib import Path

from shared.circle_client import get_circle_client
from shared.config import get_settings
from shared.envfile import upsert_env_values
from shared.provisioning import ensure_circle_wallet_set_id


def main() -> None:
    settings = get_settings()
    env_path = Path(".env")
    if not env_path.exists():
        example = Path(".env.example")
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    if not settings.circle_entity_secret:
        raise RuntimeError(
            "CIRCLE_ENTITY_SECRET is missing. Run `python -m shared.register_entity_secret` first."
        )

    wallet_set_id = ensure_circle_wallet_set_id()
    upsert_env_values(env_path, {"CIRCLE_WALLET_SET_ID": wallet_set_id})
    print(f"CIRCLE_WALLET_SET_ID={wallet_set_id}")


if __name__ == "__main__":
    main()
