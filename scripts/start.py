#!/usr/bin/env python3
"""
Production startup script.
1. Seeds the database (idempotent)
2. Launches both uvicorn servers (API on $PORT, Seller on internal port)
3. Handles graceful shutdown on SIGTERM/SIGINT
"""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.seed import seed_database


def main():
    # Seed database first (idempotent)
    print("Starting seed process...")
    try:
        seed_database()
    except Exception as e:
        print(f"Seed failed: {e}", file=sys.stderr)
        # Don't exit; continue to server startup
        # The servers may still work with an unseeded DB

    # Get ports from environment
    api_port = os.environ.get("PORT", "8000")
    seller_port = os.environ.get("SELLER_PORT", "8001")

    print(f"\n🚀 Starting servers...")
    print(f"  API server: http://0.0.0.0:{api_port}")
    print(f"  Seller agent: http://0.0.0.0:{seller_port}")

    # Start API server
    api_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.server:app",
            "--host",
            "0.0.0.0",
            "--port",
            api_port,
        ]
    )

    # Start Seller Agent server
    seller_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "seller_agent.server:app",
            "--host",
            "0.0.0.0",
            "--port",
            seller_port,
        ]
    )

    # Handle graceful shutdown
    def shutdown_handler(signum, frame):
        print("\n🛑 Shutdown signal received. Terminating servers...")
        api_proc.terminate()
        seller_proc.terminate()
        try:
            api_proc.wait(timeout=5)
            seller_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("  Force killing servers...")
            api_proc.kill()
            seller_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Wait for both processes
    print("✓ Servers started. Waiting for requests...\n")
    try:
        api_proc.wait()
        seller_proc.wait()
    except KeyboardInterrupt:
        shutdown_handler(None, None)


if __name__ == "__main__":
    main()
