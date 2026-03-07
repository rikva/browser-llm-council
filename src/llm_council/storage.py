"""Simple SQLite storage for council session history."""

import json
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.path.expanduser("~/.llm-council-history.db"))


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            providers TEXT NOT NULL,
            chairman TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            provider TEXT NOT NULL,
            stage INTEGER NOT NULL,
            text TEXT NOT NULL,
            html TEXT NOT NULL DEFAULT '',
            UNIQUE(session_id, provider, stage)
        );
        CREATE TABLE IF NOT EXISTS synthesis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE REFERENCES sessions(id),
            text TEXT NOT NULL,
            html TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.close()


def create_session(question: str, providers: list[str], chairman: str) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO sessions (question, providers, chairman, created_at) VALUES (?, ?, ?, ?)",
        (question, json.dumps(providers), chairman, datetime.now(timezone.utc).isoformat()),
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def save_response(session_id: int, provider: str, stage: int, text: str, html: str = ""):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO responses (session_id, provider, stage, text, html) VALUES (?, ?, ?, ?, ?)",
        (session_id, provider, stage, text, html),
    )
    conn.commit()
    conn.close()


def save_synthesis(session_id: int, text: str, html: str = ""):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO synthesis (session_id, text, html) VALUES (?, ?, ?)",
        (session_id, text, html),
    )
    conn.commit()
    conn.close()


def list_sessions(limit: int = 50) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, question, providers, chairman, created_at FROM sessions ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "question": r["question"],
            "providers": json.loads(r["providers"]),
            "chairman": r["chairman"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_session(session_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT id, question, providers, chairman, created_at FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None

    responses = conn.execute(
        "SELECT provider, stage, text, html FROM responses WHERE session_id = ? ORDER BY stage, provider",
        (session_id,),
    ).fetchall()

    synth = conn.execute(
        "SELECT text, html FROM synthesis WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    conn.close()

    return {
        "id": row["id"],
        "question": row["question"],
        "providers": json.loads(row["providers"]),
        "chairman": row["chairman"],
        "created_at": row["created_at"],
        "responses": [
            {"provider": r["provider"], "stage": r["stage"], "text": r["text"], "html": r["html"]}
            for r in responses
        ],
        "synthesis": {"text": synth["text"], "html": synth["html"]} if synth else None,
    }
