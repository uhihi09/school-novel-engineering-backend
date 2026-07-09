"""Connectivity check + schema bootstrap for the configured DATABASE_URL.

Reads DATABASE_URL from your .env / environment (falls back to the local SQLite default),
verifies the connection, then creates all tables (Users / InequalityReports / SimulationLogs).

Usage:
    # after setting DATABASE_URL in .env (e.g. Cloud SQL Postgres):
    python scripts/init_db.py
"""
import sys
from pathlib import Path

# Make the project root importable when run as `python scripts/init_db.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text

from app.db.session import Base, engine

# Import models so they register on Base.metadata before create_all.
from app.db import models  # noqa: F401  (side-effect import)


def main() -> int:
    print(f"Target: {engine.url.render_as_string(hide_password=True)}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connection OK")
    except Exception as exc:  # noqa: BLE001 — surface any driver/network/auth error plainly
        print(f"Connection FAILED: {exc}")
        print(
            "\nHints:\n"
            "  • Postgres: is DATABASE_URL set and DB_PASSWORD filled in?\n"
            "  • Public IP: is your client IP in the instance's Authorized networks?\n"
            "  • Or start the Cloud SQL Auth Proxy and use the 127.0.0.1 URL."
        )
        return 1

    Base.metadata.create_all(bind=engine)
    tables = inspect(engine).get_table_names()
    print("Tables created/verified:", ", ".join(sorted(tables)) or "(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
