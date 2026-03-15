#!/usr/bin/env python3
"""
Database migration runner.

Usage:
    uv run db_loaders/migrate.py                    # apply all pending migrations
    uv run db_loaders/migrate.py --mark-applied 1   # bootstrap: record V001 as applied
                                                    # without executing it (for existing
                                                    # installations where the schema is
                                                    # already up to date)

Migration files live in migrations/ at the project root and follow the naming
convention:

    V{NNN}__{description}.sql   — SQL migration (may contain multiple statements
                                  separated by semicolons)
    V{NNN}__{description}.py    — Python migration; must expose run(cnx) where cnx
                                  is a mysql.connector connection. The runner commits
                                  after run() returns; raise an exception to abort.

Each applied migration is recorded in the schema_migration table with its version
number. Migrations are never re-applied.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils import db as db_utils  # noqa: E402

MIGRATIONS_DIR = ROOT / "migrations"

_CREATE_MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version     INT          NOT NULL PRIMARY KEY,
    description VARCHAR(200) NOT NULL,
    applied_at  DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL
) ENGINE = InnoDB
"""


# ---------------------------------------------------------------------------
# Internal helpers — all take a raw mysql.connector connection
# ---------------------------------------------------------------------------

def _ensure_migration_table(cnx):
    cur = cnx.cursor()
    try:
        cur.execute(_CREATE_MIGRATION_TABLE)
        cnx.commit()
    finally:
        cur.close()


def _get_applied_versions(cnx) -> set[int]:
    cur = cnx.cursor()
    try:
        cur.execute("SELECT version FROM schema_migration")
        return {row[0] for row in cur.fetchall()}
    finally:
        cur.close()


def _record_version(cnx, version: int, description: str):
    cur = cnx.cursor()
    try:
        cur.execute(
            "INSERT INTO schema_migration (version, description) VALUES (%s, %s)",
            (version, description),
        )
        cnx.commit()
    finally:
        cur.close()


def _parse_filename(path: Path) -> tuple[int, str] | None:
    """V001__some_description.sql → (1, 'some description'), or None if unrecognised."""
    stem = path.stem
    if not stem.startswith("V"):
        return None
    parts = stem.split("__", 1)
    if len(parts) != 2:
        return None
    try:
        version = int(parts[0][1:])
        description = parts[1].replace("_", " ")
        return version, description
    except ValueError:
        return None


def _apply_sql(cnx, path: Path):
    sql = path.read_text(encoding="utf-8")
    cur = cnx.cursor()
    try:
        # multi=True handles semicolon-separated statements in a single file
        for result in cur.execute(sql, multi=True):
            if result.with_rows:
                result.fetchall()  # consume to avoid "commands out of sync"
        cnx.commit()
    finally:
        cur.close()


def _apply_python(cnx, path: Path):
    spec = importlib.util.spec_from_file_location("migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise AttributeError(f"{path.name} must expose a run(cnx) function")
    module.run(cnx)
    cnx.commit()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_pending_migrations():
    cnx = db_utils.cnx_pool.get_connection()
    try:
        _ensure_migration_table(cnx)
        applied = _get_applied_versions(cnx)

        candidates: list[tuple[int, str, Path]] = []
        for path in MIGRATIONS_DIR.iterdir():
            if path.suffix not in (".sql", ".py"):
                continue
            parsed = _parse_filename(path)
            if parsed is None:
                print(f"  [SKIP] Unrecognised filename: {path.name}")
                continue
            candidates.append((parsed[0], parsed[1], path))

        candidates.sort(key=lambda x: x[0])
        pending = [(v, d, p) for v, d, p in candidates if v not in applied]

        if not pending:
            print("Database is up to date — no pending migrations.")
            return

        for version, description, path in pending:
            print(f"  Applying V{version:03d}: {description} ...", end=" ", flush=True)
            try:
                if path.suffix == ".sql":
                    _apply_sql(cnx, path)
                else:
                    _apply_python(cnx, path)
                _record_version(cnx, version, description)
                print("done.")
            except Exception as e:
                print(f"FAILED.\n  Error: {e}")
                print("  Stopping. Fix the migration and re-run.")
                sys.exit(1)

        print(f"\n{len(pending)} migration(s) applied.")
    finally:
        cnx.close()


def mark_applied(version: int):
    """Record a migration version as applied without executing it."""
    cnx = db_utils.cnx_pool.get_connection()
    try:
        _ensure_migration_table(cnx)
        applied = _get_applied_versions(cnx)
        if version in applied:
            print(f"V{version:03d} is already recorded as applied.")
            return

        # Find the description from the file, if present
        description = f"manually marked applied"
        for path in MIGRATIONS_DIR.iterdir():
            parsed = _parse_filename(path)
            if parsed and parsed[0] == version:
                description = parsed[1]
                break

        _record_version(cnx, version, description)
        print(f"V{version:03d} recorded as applied.")
    finally:
        cnx.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--mark-applied":
        try:
            mark_applied(int(args[1]))
        except ValueError:
            print("Usage: migrate.py --mark-applied <version_number>")
            sys.exit(1)
    elif not args:
        run_pending_migrations()
    else:
        print("Usage:")
        print("  uv run db_loaders/migrate.py")
        print("  uv run db_loaders/migrate.py --mark-applied <version_number>")
        sys.exit(1)
