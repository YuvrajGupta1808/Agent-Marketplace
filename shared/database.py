from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from shared.config import get_settings


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def initialize_database() -> None:
    db_path = get_settings().database_file
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                external_id TEXT UNIQUE,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallets (
                id TEXT PRIMARY KEY,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                circle_wallet_id TEXT NOT NULL UNIQUE,
                wallet_set_id TEXT NOT NULL,
                blockchain TEXT NOT NULL,
                account_type TEXT NOT NULL,
                address TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                endpoint_url TEXT,
                wallet_id TEXT NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                buyer_agent_id TEXT NOT NULL,
                seller_agent_id TEXT NOT NULL,
                circle_transaction_id TEXT NOT NULL UNIQUE,
                amount_usdc TEXT NOT NULL,
                tx_hash TEXT,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            """
        )
        connection.commit()

        # Migrate existing databases: add description and system_prompt columns if not present
        for col, col_type in [("description", "TEXT NOT NULL DEFAULT ''"),
                              ("system_prompt", "TEXT NOT NULL DEFAULT ''")]:
            try:
                connection.execute(f"ALTER TABLE agents ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # One-time repair: recover seller tool mappings after accidental global overwrite.
        # This migration is gated so it never rewrites sellers again after first successful run.
        repaired = connection.execute(
            "SELECT value FROM app_config WHERE key = 'seller_tools_repaired_v1'"
        ).fetchone()
        if not repaired:
            seller_rows = connection.execute(
                "SELECT id, name, metadata_json FROM agents WHERE role = 'seller'"
            ).fetchall()
            for row in seller_rows:
                try:
                    metadata = json.loads(row[2] or "{}")
                except (TypeError, json.JSONDecodeError):
                    metadata = {}

                name = str(row[1] or "").strip().lower()
                existing_tools = metadata.get("built_in_tools")
                if not isinstance(existing_tools, list):
                    existing_tools = metadata.get("tool_ids")
                if not isinstance(existing_tools, list):
                    existing_tools = []

                # Preserve existing non-empty assignments by default.
                next_tools = [str(tool).strip() for tool in existing_tools if str(tool).strip()]

                # Apply expected defaults for known marketplace sellers.
                if "duckduckgo" in name:
                    next_tools = ["web_search"]
                elif "geography" in name and "weather" in name:
                    next_tools = ["tavily_search", "open_meteo_weather"]
                elif "yutori" in name:
                    next_tools = ["yutori_research"]
                elif "utility" in name:
                    next_tools = ["json_api_fetcher"]

                # Dedupe while preserving order.
                seen: set[str] = set()
                deduped_tools: list[str] = []
                for tool in next_tools:
                    if tool in seen:
                        continue
                    seen.add(tool)
                    deduped_tools.append(tool)

                metadata["built_in_tools"] = deduped_tools
                if "tool_ids" in metadata:
                    metadata.pop("tool_ids", None)
                connection.execute(
                    "UPDATE agents SET metadata_json = ? WHERE id = ?",
                    (json.dumps(metadata, sort_keys=True), row[0]),
                )

            connection.execute(
                "INSERT OR REPLACE INTO app_config (key, value, updated_at) VALUES (?, ?, ?)",
                ("seller_tools_repaired_v1", "true", utc_now()),
            )
            connection.commit()


def get_connection() -> sqlite3.Connection:
    initialize_database()
    connection = sqlite3.connect(get_settings().database_file)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_cursor() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
