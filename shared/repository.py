from __future__ import annotations

import json
import uuid
from typing import Any

from shared.database import db_cursor, initialize_database, utc_now
from shared.types import AgentRecord, CreateAgentRequest, CreateUserRequest, UserRecord, WalletRecord

class MarketplaceRepository:
    def __init__(self) -> None:
        initialize_database()

    def get_app_config(self, key: str) -> str | None:
        with db_cursor() as connection:
            row = connection.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_app_config(self, key: str, value: str) -> None:
        now = utc_now()
        with db_cursor() as connection:
            connection.execute(
                """
                INSERT INTO app_config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def delete_app_config(self, key: str) -> None:
        with db_cursor() as connection:
            connection.execute("DELETE FROM app_config WHERE key = ?", (key,))

    def create_user(self, request: CreateUserRequest) -> UserRecord:
        user = UserRecord(
            id=str(uuid.uuid4()),
            external_id=request.external_id,
            display_name=request.display_name,
            created_at=utc_now(),
        )
        with db_cursor() as connection:
            connection.execute(
                "INSERT INTO users (id, external_id, display_name, created_at) VALUES (?, ?, ?, ?)",
                (user.id, user.external_id, user.display_name, user.created_at),
            )
        return user

    def list_users(self) -> list[UserRecord]:
        with db_cursor() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY created_at DESC"
            ).fetchall()
        return [UserRecord(**dict(row)) for row in rows]

    def get_user(self, user_id: str) -> UserRecord:
        with db_cursor() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise KeyError(f"User {user_id} not found.")
        return UserRecord(**dict(row))

    def list_agents_for_user(self, user_id: str) -> list[AgentRecord]:
        return self.list_agents(user_id=user_id)

    def list_agents(
        self,
        *,
        user_id: str | None = None,
        role: str | None = None,
    ) -> list[AgentRecord]:
        conditions: list[str] = []
        params: list[str] = []
        if user_id:
            conditions.append("a.user_id = ?")
            params.append(user_id)
        if role:
            conditions.append("a.role = ?")
            params.append(role)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with db_cursor() as connection:
            rows = connection.execute(
                """
                SELECT
                    a.id,
                    a.user_id,
                    a.role,
                    a.name,
                    a.endpoint_url,
                    a.wallet_id,
                    a.created_at,
                    a.metadata_json,
                    w.circle_wallet_id,
                    w.wallet_set_id,
                    w.blockchain,
                    w.account_type,
                    w.address
                FROM agents a
                JOIN wallets w ON w.id = a.wallet_id
                {where_clause}
                ORDER BY a.created_at ASC
                """.format(where_clause=where_clause),
                tuple(params),
            ).fetchall()
        return [self._agent_from_row(row) for row in rows]

    def create_agent(
        self,
        request: CreateAgentRequest,
        wallet: Any,
    ) -> AgentRecord:
        agent_id = str(uuid.uuid4())
        wallet_id = str(uuid.uuid4())
        created_at = utc_now()
        metadata_json = json.dumps(request.metadata, sort_keys=True)
        wallet_metadata = json.dumps(wallet.metadata, sort_keys=True)

        with db_cursor() as connection:
            connection.execute(
                """
                INSERT INTO wallets (
                    id, owner_type, owner_id, circle_wallet_id, wallet_set_id, blockchain,
                    account_type, address, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wallet_id,
                    "agent",
                    agent_id,
                    wallet.circle_wallet_id,
                    wallet.wallet_set_id,
                    wallet.blockchain,
                    wallet.account_type,
                    wallet.address,
                    created_at,
                    wallet_metadata,
                ),
            )
            connection.execute(
                """
                INSERT INTO agents (id, user_id, role, name, endpoint_url, wallet_id, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    request.user_id,
                    request.role,
                    request.name,
                    request.endpoint_url,
                    wallet_id,
                    created_at,
                    metadata_json,
                ),
            )
            row = connection.execute(
                """
                SELECT
                    a.id,
                    a.user_id,
                    a.role,
                    a.name,
                    a.endpoint_url,
                    a.wallet_id,
                    a.created_at,
                    a.metadata_json,
                    w.circle_wallet_id,
                    w.wallet_set_id,
                    w.blockchain,
                    w.account_type,
                    w.address
                FROM agents a
                JOIN wallets w ON w.id = a.wallet_id
                WHERE a.id = ?
                """,
                (agent_id,),
            ).fetchone()

        return self._agent_from_row(row)

    def get_agent(self, agent_id: str) -> AgentRecord:
        with db_cursor() as connection:
            row = connection.execute(
                """
                SELECT
                    a.id,
                    a.user_id,
                    a.role,
                    a.name,
                    a.endpoint_url,
                    a.wallet_id,
                    a.created_at,
                    a.metadata_json,
                    w.circle_wallet_id,
                    w.wallet_set_id,
                    w.blockchain,
                    w.account_type,
                    w.address
                FROM agents a
                JOIN wallets w ON w.id = a.wallet_id
                WHERE a.id = ?
                """,
                (agent_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"Agent {agent_id} not found.")
        return self._agent_from_row(row)

    def get_wallet(self, wallet_id: str) -> WalletRecord:
        with db_cursor() as connection:
            row = connection.execute("SELECT * FROM wallets WHERE id = ?", (wallet_id,)).fetchone()
        if not row:
            raise KeyError(f"Wallet {wallet_id} not found.")
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return WalletRecord(**data)

    def _agent_from_row(self, row: Any) -> AgentRecord:
        payload = dict(row)
        metadata = json.loads(payload.pop("metadata_json"))
        wallet = WalletRecord(
            id=payload.pop("wallet_id"),
            owner_type="agent",
            owner_id=payload["id"],
            circle_wallet_id=payload.pop("circle_wallet_id"),
            wallet_set_id=payload.pop("wallet_set_id"),
            blockchain=payload.pop("blockchain"),
            account_type=payload.pop("account_type"),
            address=payload.pop("address"),
            created_at=payload["created_at"],
            metadata={},
        )
        return AgentRecord(**payload, wallet=wallet, metadata=metadata)

    def save_transaction(self, thread_id: str, task_id: str, buyer_agent_id: str, seller_agent_id: str, payment: dict) -> None:
        """Store a payment transaction in the database."""
        tx_id = str(uuid.uuid4())
        created_at = utc_now()
        metadata_json = json.dumps(payment.get("metadata", {}), sort_keys=True)

        with db_cursor() as connection:
            connection.execute(
                """
                INSERT INTO transactions (
                    id, thread_id, task_id, buyer_agent_id, seller_agent_id,
                    circle_transaction_id, amount_usdc, tx_hash, state, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx_id,
                    thread_id,
                    task_id,
                    buyer_agent_id,
                    seller_agent_id,
                    payment.get("circle_transaction_id", ""),
                    payment.get("amount_usdc", "0"),
                    payment.get("tx_hash"),
                    payment.get("state", "INITIATED"),
                    created_at,
                    metadata_json,
                ),
            )

    def list_transactions(self, thread_id: str | None = None, buyer_agent_id: str | None = None) -> list[dict]:
        """Retrieve transactions, optionally filtered by thread or buyer agent."""
        conditions: list[str] = []
        params: list[str] = []

        if thread_id:
            conditions.append("thread_id = ?")
            params.append(thread_id)
        if buyer_agent_id:
            conditions.append("buyer_agent_id = ?")
            params.append(buyer_agent_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with db_cursor() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM transactions
                {where_clause}
                ORDER BY created_at DESC
                """,
                tuple(params),
            ).fetchall()

        return [
            {
                **dict(row),
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in rows
        ]


repository = MarketplaceRepository()
