"""
botlite.db
~~~~~~~~~~
Thin SQLite layer: ban list and download counters.
"""

from __future__ import annotations

import sqlite3

from botlite.config import DB_FILE


def init() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.executescript("""
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
        """)


def _execute(query: str, params: tuple = (), *, fetch: bool = False):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute(query, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
    return None


# ── Ban management ────────────────────────────────────────────────────────────

def is_banned(uid: int) -> bool:
    return bool(_execute("SELECT 1 FROM banned_users WHERE user_id=?", (uid,), fetch=True))


def ban(uid: int) -> None:
    _execute("INSERT OR REPLACE INTO banned_users (user_id) VALUES (?)", (uid,))


def unban(uid: int) -> None:
    _execute("DELETE FROM banned_users WHERE user_id=?", (uid,))


# ── Stats ─────────────────────────────────────────────────────────────────────

def increment(name: str) -> None:
    _execute("UPDATE stats SET value=value+1 WHERE name=?", (name,))


def get_stat(name: str) -> int:
    rows = _execute("SELECT value FROM stats WHERE name=?", (name,), fetch=True)
    return rows[0][0] if rows else 0
