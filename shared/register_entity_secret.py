from __future__ import annotations

import argparse
import secrets
from pathlib import Path

from circle.web3 import utils

from shared.config import get_settings
from shared.envfile import upsert_env_values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and register a Circle Entity Secret, then persist it to .env.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the env file to update. Defaults to .env.",
    )
    parser.add_argument(
        "--recovery-dir",
        default="output/circle-recovery",
        help="Directory where the Circle recovery file will be written.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite any existing CIRCLE_ENTITY_SECRET in the env file.",
    )
    return parser.parse_args()


def ensure_env_file(path: Path) -> None:
    if path.exists():
        return

    example = Path(".env.example")
    if example.exists():
        path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        path.write_text("", encoding="utf-8")


def main() -> None:
    args = parse_args()
    settings = get_settings()
    env_path = Path(args.env_file)
    recovery_dir = Path(args.recovery_dir)

    if not settings.circle_api_key:
        raise RuntimeError("CIRCLE_API_KEY is required before registering an Entity Secret.")

    if settings.circle_entity_secret and not args.force:
        raise RuntimeError(
            "CIRCLE_ENTITY_SECRET is already set. Re-run with --force only if you intend to rotate it."
        )

    ensure_env_file(env_path)
    recovery_dir.mkdir(parents=True, exist_ok=True)

    entity_secret = secrets.token_hex(32)
    utils.register_entity_secret_ciphertext(
        api_key=settings.circle_api_key.get_secret_value(),
        entity_secret=entity_secret,
        recoveryFileDownloadPath=str(recovery_dir),
    )

    upsert_env_values(env_path, {"CIRCLE_ENTITY_SECRET": entity_secret})

    print("Entity Secret registered successfully.")
    print(f"Updated env file: {env_path}")
    print(f"Recovery files saved to: {recovery_dir}")
    print("Store the recovery file and the entity secret securely.")


if __name__ == "__main__":
    main()
