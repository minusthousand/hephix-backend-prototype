from typing import List, Optional

from pydantic import BaseModel


# ---------- Chat ----------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str


# ---------- Sessions ----------

class SessionInfo(BaseModel):
    session_id: str
    updated_at: float


class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[dict]
