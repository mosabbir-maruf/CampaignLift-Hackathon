"""Database connection and session management for CampaignLift backend.

Canonical planning sources:
- planning/architecture_plan.md (Persistence: SQLite file for campaign definitions)
- planning/backend_plan.md
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator, Optional

from backend.app.settings import Settings, get_settings, REPO_ROOT


def get_sqlite_path(database_url: str) -> str:
    """Extract SQLite database file path from a database URL."""
    if database_url == ":memory:":
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        raw_path = database_url.replace("sqlite:///", "")
        p = Path(raw_path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return str(p)
    if database_url.startswith("sqlite://"):
        raw_path = database_url.replace("sqlite://", "")
        p = Path(raw_path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return str(p)
    # Raw file path
    p = Path(database_url)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return str(p)


def get_connection(settings: Optional[Settings] = None) -> sqlite3.Connection:
    """Create a SQLite database connection with row factory enabled."""
    if settings is None:
        settings = get_settings()

    db_path = get_sqlite_path(settings.database_url)

    if db_path != ":memory:":
        parent_dir = Path(db_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(settings: Optional[Settings] = None) -> None:
    """Initialize database schema tables for health and persistence."""
    conn = get_connection(settings)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS _health_check (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def check_database_writable(settings: Optional[Settings] = None) -> bool:
    """Verify that the database is usable and writable."""
    try:
        conn = get_connection(settings)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS _health_check (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("INSERT INTO _health_check DEFAULT VALUES")
            inserted_id = cursor.lastrowid
            conn.commit()
            if inserted_id:
                cursor.execute("DELETE FROM _health_check WHERE id = ?", (inserted_id,))
                conn.commit()
            return True
        finally:
            conn.close()
    except Exception:
        return False


from fastapi import Depends

def get_db(
    settings: Settings = Depends(get_settings),
) -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency yielding a managed database connection."""
    conn = get_connection(settings)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
