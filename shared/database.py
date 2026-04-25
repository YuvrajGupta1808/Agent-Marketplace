from __future__ import annotations

import sqlite3
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
