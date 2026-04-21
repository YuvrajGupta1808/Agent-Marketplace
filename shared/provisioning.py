from __future__ import annotations

import uuid

from shared.circle_client import get_circle_client
from shared.config import get_settings
from shared.repository import repository


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def ensure_circle_wallet_set_id() -> str:
    settings = get_settings()
    if settings.circle_wallet_set_id and _is_uuid(settings.circle_wallet_set_id):
        repository.set_app_config("circle_wallet_set_id", settings.circle_wallet_set_id)
        return settings.circle_wallet_set_id

    persisted = repository.get_app_config("circle_wallet_set_id")
    if persisted and _is_uuid(persisted):
        return persisted
    if persisted and not _is_uuid(persisted):
        repository.delete_app_config("circle_wallet_set_id")

    wallet_set_id = get_circle_client().create_wallet_set("Agent Marketplace")
    repository.set_app_config("circle_wallet_set_id", wallet_set_id)
    return wallet_set_id
