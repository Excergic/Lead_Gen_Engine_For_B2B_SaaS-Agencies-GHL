#!/usr/bin/env python3
"""Drop public schema and re-apply all SQL migrations (full wipe + fresh schema)."""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"

# Reuse connection helper from run_migrations
sys.path.insert(0, str(ROOT / "scripts"))
from run_migrations import _connect_kwargs, _migration_files  # noqa: E402


def _reset_schema(cur: psycopg.Cursor) -> None:
    print("Dropping public schema (all tables + data)...")
    cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
    cur.execute("CREATE SCHEMA public;")
    cur.execute("GRANT ALL ON SCHEMA public TO postgres;")
    cur.execute("GRANT ALL ON SCHEMA public TO public;")
    print("  ✓ public schema recreated")


def main() -> None:
    load_dotenv(ROOT / ".env")
    files = _migration_files()
    connect_kwargs = _connect_kwargs()

    print("Connecting to Supabase Postgres...")
    with psycopg.connect(**connect_kwargs, autocommit=True) as conn:
        with conn.cursor() as cur:
            _reset_schema(cur)
            for path in files:
                sql = path.read_text()
                print(f"Applying {path.name}...")
                cur.execute(sql)
                print(f"  ✓ {path.name}")

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]
            print("\nPublic tables:", ", ".join(tables) if tables else "(none)")
            print("\nDone — database wiped and migrations applied.")


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error as exc:
        print(f"Reset failed: {exc}", file=sys.stderr)
        sys.exit(1)
