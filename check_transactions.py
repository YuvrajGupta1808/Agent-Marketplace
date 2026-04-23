#!/usr/bin/env python3
"""Check transaction database after running a workflow."""
import sqlite3
import time
from pathlib import Path

def check_transactions():
    db_path = Path("data/marketplace.db")

    while True:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM transactions;")
            count = cursor.fetchone()[0]

            cursor.execute("SELECT task_id, amount_usdc, state, created_at FROM transactions ORDER BY created_at DESC LIMIT 5;")
            rows = cursor.fetchall()

            print(f"\n{'='*60}")
            print(f"Transactions in DB: {count}")
            print(f"{'='*60}")

            if rows:
                print("\nLatest transactions:")
                for task_id, amount, state, created_at in rows:
                    print(f"  • Task: {task_id}")
                    print(f"    Amount: {amount} USDC")
                    print(f"    State: {state}")
                    print(f"    Time: {created_at}")
                    print()
            else:
                print("No transactions yet. Run a workflow to create some.")

            conn.close()
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(3)

if __name__ == "__main__":
    print("Monitoring database for transactions...")
    print("Run a workflow on the dashboard, and changes will appear below every 3 seconds")
    check_transactions()
