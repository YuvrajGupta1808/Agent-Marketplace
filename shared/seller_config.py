from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from shared.builtin_tools import list_builtin_tools
from shared.circle_client import format_usdc_amount
from shared.config import get_settings
from shared.types import AgentRecord

DEFAULT_SELLER_TOOL_IDS: list[str] = []
DEFAULT_SELLER_CATEGORY = "Research"


def normalize_tool_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return list(DEFAULT_SELLER_TOOL_IDS)

    known_tool_ids = {tool.id for tool in list_builtin_tools()}
    normalized: list[str] = []
    for tool_id in value:
        if not isinstance(tool_id, str):
            continue
        cleaned = tool_id.strip()
        if not cleaned or cleaned in normalized:
            continue
        if cleaned in known_tool_ids:
            normalized.append(cleaned)
    return normalized


def normalize_price_usdc(value: Any) -> str:
    fallback = format_usdc_amount(get_settings().seller_price_usdc)
    if value is None or value == "":
        return fallback

    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return fallback

    if price <= 0:
        return fallback
    return format_usdc_amount(price)


def normalize_seller_metadata(metadata: dict[str, Any], *, status: str | None = None) -> dict[str, Any]:
    normalized = dict(metadata)
    requested_status = status or str(normalized.get("status") or "draft").lower()
    if requested_status not in {"draft", "published", "disabled"}:
        requested_status = "draft"

    tool_ids = normalize_tool_ids(normalized.get("built_in_tools") or normalized.get("tool_ids"))

    normalized.update(
        {
            "seller_type": normalized.get("seller_type") or "hosted",
            "status": requested_status,
            "price_usdc": normalize_price_usdc(normalized.get("price_usdc")),
            "category": str(normalized.get("category") or DEFAULT_SELLER_CATEGORY).strip() or DEFAULT_SELLER_CATEGORY,
            "use_case": str(normalized.get("use_case") or normalized.get("description") or "").strip(),
            "built_in_tools": tool_ids,
        }
    )
    return normalized


def seller_status(seller: AgentRecord) -> str:
    status = str(seller.metadata.get("status") or "published").lower()
    return status if status in {"draft", "published", "disabled"} else "published"


def is_seller_published(seller: AgentRecord) -> bool:
    return seller_status(seller) == "published"


def seller_price_usdc(seller: AgentRecord) -> str:
    return normalize_price_usdc(seller.metadata.get("price_usdc"))


def seller_tool_ids(seller: AgentRecord) -> list[str]:
    return normalize_tool_ids(seller.metadata.get("built_in_tools") or seller.metadata.get("tool_ids"))
