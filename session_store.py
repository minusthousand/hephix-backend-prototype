"""
SQLite-backed session / message-history store.

Stores LangChain message history per session_id so that the agent
can maintain multi-turn conversations.
"""

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict


class SQLiteSessionStore:
    """Low-level key/value store backed by SQLite (WAL mode)."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        path = Path(self._db_path)
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    async def get(self, session_id: str) -> Optional[str]:
        def _get() -> Optional[str]:
            with sqlite3.connect(self._db_path, timeout=30.0) as conn:
                cur = conn.execute(
                    "SELECT data FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = cur.fetchone()
                return row[0] if row else None

        return await asyncio.to_thread(_get)

    async def set(self, session_id: str, data: str) -> None:
        def _set() -> None:
            with sqlite3.connect(self._db_path, timeout=30.0) as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, data, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        data = excluded.data,
                        updated_at = excluded.updated_at
                    """,
                    (session_id, data, time.time()),
                )

        await asyncio.to_thread(_set)

    async def delete(self, session_id: str) -> None:
        def _delete() -> None:
            with sqlite3.connect(self._db_path, timeout=30.0) as conn:
                conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,),
                )

        await asyncio.to_thread(_delete)

    async def list(self, limit: int = 100, offset: int = 0) -> list[tuple[str, float]]:
        def _list() -> list[tuple[str, float]]:
            with sqlite3.connect(self._db_path, timeout=30.0) as conn:
                cur = conn.execute(
                    """
                    SELECT session_id, updated_at
                    FROM sessions
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
                return [(row[0], row[1]) for row in cur.fetchall()]

        return await asyncio.to_thread(_list)


class SQLiteMessageHistoryStore:
    """High-level store that serialises LangChain messages into SQLite."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = os.getenv("SESSION_DB_PATH", "sessions.db")
        self._store = SQLiteSessionStore(db_path)

    async def get(self, session_id: str) -> Optional[list[BaseMessage]]:
        data = await self._store.get(session_id)
        if data is None:
            return None
        try:
            payload = json.loads(data)
            if not isinstance(payload, list):
                return None
            return messages_from_dict(payload)
        except Exception:
            return None

    async def get_or_create(
        self,
        session_id: str,
        factory: Callable[[], Sequence[BaseMessage]],
    ) -> list[BaseMessage]:
        history = await self.get(session_id)
        if history is None:
            history = list(factory())
            await self.set(session_id, history)
        return history

    async def set(self, session_id: str, value: Sequence[BaseMessage]) -> None:
        data = json.dumps(messages_to_dict(list(value)))
        await self._store.set(session_id, data)

    async def delete(self, session_id: str) -> None:
        await self._store.delete(session_id)

    async def list_sessions(
        self, limit: int = 100, offset: int = 0
    ) -> list[tuple[str, float]]:
        return await self._store.list(limit=limit, offset=offset)

    async def get_serialized(self, session_id: str) -> Optional[list[dict]]:
        history = await self.get(session_id)
        if history is None:
            return None
        return messages_to_dict(history)

