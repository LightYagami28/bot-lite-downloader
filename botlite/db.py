"""Thin SQLite layer for the ban list and download counters."""

from __future__ import annotations

import sqlite3
from typing import Any

from botlite.config import DB_FILE

_SCHEMA = """
CREATE TABLE IF NOT EXISTS banned_users (
    user_id   INTEGER PRIMARY KEY,
    banned_at TEXT    DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS stats (
    name  TEXT    PRIMARY KEY,
    value INTEGER DEFAULT 0
);
INSERT OR IGNORE INTO stats (name, value) VALUES
    ('total_downloads',  0),
    ('failed_downloads', 0);
"""


def init() -> None:
    """Create the SQLite schema and default counters when they are missing.

    Raises:
        sqlite3.Error: When the database cannot be opened or migrated.
    """
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _execute(
    query: str,
    params: tuple[Any, ...] = (),
    *,
    fetch: bool = False,
) -> Any:
    """Run a statement against a fresh connection.

    Args:
        query: SQL statement to execute.
        params: Positional parameters for the statement.
        fetch: When ``True`` return the rows instead of committing.

    Returns:
        Query result (rows for SELECT, ``None`` otherwise).

    Raises:
        sqlite3.Error: When the statement fails.
    """
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.execute(query, params)
        if fetch:
            return cursor.fetchall()
        conn.commit()
        return None
    finally:
        conn.close()


def is_banned(uid: int) -> bool:
    """Return whether *uid* is present in the ban list.

    Args:
        uid: Telegram user identifier.

    Returns:
        ``True`` when the user is banned.
    """
    return bool(_execute("SELECT 1 FROM banned_users WHERE user_id=?", (uid,), fetch=True))


def ban(uid: int) -> None:
    """Add *uid* to the ban list.

    Args:
        uid: Telegram user identifier to ban.
    """
    _execute("INSERT OR REPLACE INTO banned_users (user_id) VALUES (?)", (uid,))


def unban(uid: int) -> None:
    """Remove *uid* from the ban list.

    Args:
        uid: Telegram user identifier to unban.
    """
    _execute("DELETE FROM banned_users WHERE user_id=?", (uid,))


def increment(name: str) -> None:
    """Increment the download counter *name* by one.

    Args:
        name: Counter name (e.g. ``total_downloads`` or ``failed_downloads``).
    """
    _execute("UPDATE stats SET value=value+1 WHERE name=?", (name,))


def get_stat(name: str) -> int:
    """Return the current value of the counter *name*.

    Args:
        name: Counter name.

    Returns:
        Counter value (0 when the counter is missing).
    """
    rows = _execute("SELECT value FROM stats WHERE name=?", (name,), fetch=True)
    return rows[0][0] if rows else 0
