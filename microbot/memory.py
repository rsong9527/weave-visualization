"""Conversation memory with SQLite persistence.

Features:
  - Save/load conversation sessions
  - List and search sessions
  - Auto-save on exit
  - Session metadata (title, timestamps, message count)
"""

import json
import sqlite3
import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from microbot.config import DB_FILE, CONFIG_DIR
from microbot.llm import Message


# =========================================================================
# Data types
# =========================================================================

@dataclass
class SessionInfo:
    """Metadata for a conversation session."""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int

    def summary(self) -> str:
        return f"[{self.session_id[:8]}] {self.title}  ({self.message_count} msgs, {self.updated_at})"


# =========================================================================
# Memory store
# =========================================================================

class Memory:
    """SQLite-backed conversation memory."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_FILE
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'Untitled',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                message_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tool_calls TEXT,
                tool_call_id TEXT,
                name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id);
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def create_session(self, session_id: str, title: str = "Untitled") -> None:
        """Create a new session."""
        now = _now()
        self.conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, title, created_at, updated_at, message_count) "
            "VALUES (?, ?, ?, ?, 0)",
            (session_id, title, now, now),
        )
        self.conn.commit()

    def save_messages(self, session_id: str, messages: list[Message], title: str = "") -> None:
        """Save all messages for a session (replaces existing)."""
        now = _now()

        # Ensure session exists
        existing = self.conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

        if not existing:
            self.create_session(session_id, title or _auto_title(messages))

        # Clear old messages
        self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

        # Insert new messages
        for msg in messages:
            if msg.role == "system":
                continue  # Don't persist system prompts
            self.conn.execute(
                "INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, name, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    msg.role,
                    msg.content or "",
                    json.dumps(msg.tool_calls) if msg.tool_calls else None,
                    msg.tool_call_id,
                    msg.name,
                    now,
                ),
            )

        # Update session metadata
        actual_title = title or _auto_title(messages)
        msg_count = len([m for m in messages if m.role != "system"])
        self.conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ?, message_count = ? WHERE session_id = ?",
            (actual_title, now, msg_count, session_id),
        )
        self.conn.commit()

    def load_messages(self, session_id: str) -> list[Message]:
        """Load messages for a session."""
        rows = self.conn.execute(
            "SELECT role, content, tool_calls, tool_call_id, name FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        messages = []
        for row in rows:
            tool_calls = json.loads(row["tool_calls"]) if row["tool_calls"] else None
            messages.append(Message(
                role=row["role"],
                content=row["content"],
                tool_calls=tool_calls,
                tool_call_id=row["tool_call_id"],
                name=row["name"],
            ))
        return messages

    def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        """List recent sessions."""
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            SessionInfo(
                session_id=r["session_id"],
                title=r["title"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                message_count=r["message_count"],
            )
            for r in rows
        ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor = self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def search_sessions(self, query: str, limit: int = 10) -> list[SessionInfo]:
        """Search sessions by title or message content."""
        # Search in titles
        title_rows = self.conn.execute(
            "SELECT DISTINCT s.* FROM sessions s "
            "WHERE s.title LIKE ? "
            "ORDER BY s.updated_at DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()

        # Search in message content
        content_rows = self.conn.execute(
            "SELECT DISTINCT s.* FROM sessions s "
            "JOIN messages m ON s.session_id = m.session_id "
            "WHERE m.content LIKE ? "
            "ORDER BY s.updated_at DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()

        # Merge and deduplicate
        seen = set()
        results = []
        for r in list(title_rows) + list(content_rows):
            if r["session_id"] not in seen:
                seen.add(r["session_id"])
                results.append(SessionInfo(
                    session_id=r["session_id"],
                    title=r["title"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    message_count=r["message_count"],
                ))
        return results[:limit]

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()


# =========================================================================
# Helpers
# =========================================================================

def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _auto_title(messages: list[Message]) -> str:
    """Generate a session title from the first user message."""
    for m in messages:
        if m.role == "user" and m.content:
            title = m.content.strip()[:60]
            if len(m.content.strip()) > 60:
                title += "..."
            return title
    return "Untitled"
