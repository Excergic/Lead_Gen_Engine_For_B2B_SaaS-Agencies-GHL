#!/usr/bin/env python3
"""Apply SQL migrations to Supabase Postgres."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"


def _project_ref(supabase_url: str) -> str:
    # https://jrjkomfvxqhlneycyrgy.supabase.co -> jrjkomfvxqhlneycyrgy
    host = supabase_url.removeprefix("https://").removeprefix("http://")
    return host.split(".")[0]


def _connect_kwargs() -> dict[str, str | int]:
    if database_url := os.getenv("DATABASE_URL"):
        return {"conninfo": database_url}

    supabase_url = os.getenv("SUPABASE_URL", "")
    password = os.getenv("SUPABASE_DB_PASSWORD")
    if not supabase_url or not password:
        raise SystemExit(
            "Missing DATABASE_URL or SUPABASE_URL + SUPABASE_DB_PASSWORD.\n"
            "Get the database password from Supabase → Project Settings → Database."
        )

    ref = _project_ref(supabase_url)
    return {
        "host": os.getenv("SUPABASE_DB_HOST", f"db.{ref}.supabase.co"),
        "port": int(os.getenv("SUPABASE_DB_PORT", "5432")),
        "dbname": os.getenv("SUPABASE_DB_NAME", "postgres"),
        "user": os.getenv("SUPABASE_DB_USER", "postgres"),
        "password": password,
        "sslmode": "require",
    }


def _migration_files() -> list[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"No migration files found in {MIGRATIONS_DIR}")
    return files


def main() -> None:
    load_dotenv(ROOT / ".env")

    files = _migration_files()
    connect_kwargs = _connect_kwargs()

    print("Connecting to Supabase Postgres...")
    with psycopg.connect(**connect_kwargs, autocommit=True) as conn:
        with conn.cursor() as cur:
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


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
