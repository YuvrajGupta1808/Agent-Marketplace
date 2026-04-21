from __future__ import annotations

import sys

import httpx

from shared.config import get_settings

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    Console = None
    Table = None


def main() -> None:
    settings = get_settings()
    console = Console() if Console else None
    queries = [f"Demo query {index + 1}: explain Arc use case {index + 1}" for index in range(55)]

    rows: list[tuple[str, str]] = []
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        user = client.post(f"{settings.api_base_url}/users", json={"display_name": "Demo User"}).json()["user"]
        buyer = client.post(
            f"{settings.api_base_url}/agents",
            json={"user_id": user["id"], "role": "buyer", "name": "Demo Buyer"},
        ).json()["agent"]
        seller = client.post(
            f"{settings.api_base_url}/agents",
            json={"user_id": user["id"], "role": "seller", "name": "Demo Seller"},
        ).json()["agent"]
        for index, query in enumerate(queries, start=1):
            response = client.post(
                f"{settings.api_base_url}/run",
                json={
                    "user_goal": query,
                    "thread_id": f"demo-{index}",
                    "buyer_agent_id": buyer["id"],
                    "seller_agent_id": seller["id"],
                },
            )
            response.raise_for_status()
            data = response.json()
            tx_hashes = data.get("transaction_hashes") or []
            rows.append((query, tx_hashes[0] if tx_hashes else "missing"))

    if console and Table:
        table = Table(title="Agent Marketplace Demo")
        table.add_column("Query")
        table.add_column("Tx Hash")
        for query, tx_hash in rows:
            table.add_row(query, tx_hash)
        console.print(table)
        return

    for query, tx_hash in rows:
        print(f"{query}: {tx_hash}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        raise
