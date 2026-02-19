"""
Chat router for Hephix backend.

- POST   /chat              → AI agent conversation (Depo — default)
 - POST   /chat/darel        → AI agent conversation (Darel — separate)
 - POST   /chat/ebay         → AI agent conversation (eBay — separate)
- GET    /sessions          → list all chat sessions
- GET    /sessions/{id}     → full history for a session
- DELETE /sessions/{id}     → delete a session
"""

import os
import uuid

from fastapi import APIRouter

from schemas import ChatRequest, ChatResponse
from schemas import SessionInfo, SessionListResponse, SessionHistoryResponse
from core import (
    chat_depo,
    chat_darel,
    chat_ebay,
    new_depo_history,
    new_darel_history,
    new_ebay_history,
)
from session_store import SQLiteMessageHistoryStore

router = APIRouter()

SESSION_STORE = SQLiteMessageHistoryStore(
    os.getenv("SESSION_DB_PATH", "sessions.db")
)


# ──────────────────────────────────────────────
#  Depo chat (default)
# ──────────────────────────────────────────────

@router.options("/chat")
async def chat_options():
    return {}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """AI conversation — Claude + Depo MCP tools (default)."""
    session_id = payload.session_id or uuid.uuid4().hex
    history = await SESSION_STORE.get_or_create(session_id, new_depo_history)

    try:
        history = await chat_depo(history, payload.message)
        await SESSION_STORE.set(session_id, history)
        return ChatResponse(
            session_id=session_id,
            response=str(history[-1].content),
        )
    except Exception as e:
        return ChatResponse(
            session_id=session_id,
            response=f"Sorry, something went wrong: {e}",
        )


# ──────────────────────────────────────────────
#  Darel chat (separate endpoint)
# ──────────────────────────────────────────────

@router.options("/chat/darel")
async def chat_darel_options():
    return {}


@router.post("/chat/darel", response_model=ChatResponse)
async def chat_darel_endpoint(payload: ChatRequest) -> ChatResponse:
    """AI conversation — Claude + Darel MCP tools."""
    session_id = payload.session_id or f"darel-{uuid.uuid4().hex}"
    history = await SESSION_STORE.get_or_create(session_id, new_darel_history)

    try:
        history = await chat_darel(history, payload.message)
        await SESSION_STORE.set(session_id, history)
        return ChatResponse(
            session_id=session_id,
            response=str(history[-1].content),
        )
    except Exception as e:
        return ChatResponse(
            session_id=session_id,
            response=f"Sorry, something went wrong: {e}",
        )


# ──────────────────────────────────────────────
#  eBay chat (separate endpoint)
# ──────────────────────────────────────────────

@router.options("/chat/ebay")
async def chat_ebay_options():
    return {}


@router.post("/chat/ebay", response_model=ChatResponse)
async def chat_ebay_endpoint(payload: ChatRequest) -> ChatResponse:
    """AI conversation — Claude + eBay MCP tools."""
    session_id = payload.session_id or f"ebay-{uuid.uuid4().hex}"
    history = await SESSION_STORE.get_or_create(session_id, new_ebay_history)

    try:
        history = await chat_ebay(history, payload.message)
        await SESSION_STORE.set(session_id, history)
        return ChatResponse(
            session_id=session_id,
            response=str(history[-1].content),
        )
    except Exception as e:
        return ChatResponse(
            session_id=session_id,
            response=f"Sorry, something went wrong: {e}",
        )


# ──────────────────────────────────────────────
#  Session management
# ──────────────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(limit: int = 100, offset: int = 0) -> SessionListResponse:
    rows = await SESSION_STORE.list_sessions(limit=limit, offset=offset)
    sessions = [
        SessionInfo(session_id=sid, updated_at=updated_at)
        for sid, updated_at in rows
    ]
    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session(session_id: str) -> SessionHistoryResponse:
    messages = await SESSION_STORE.get_serialized(session_id)
    return SessionHistoryResponse(
        session_id=session_id,
        messages=messages or [],
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session by ID."""
    await SESSION_STORE.delete(session_id)
    return {"status": "deleted", "session_id": session_id}
