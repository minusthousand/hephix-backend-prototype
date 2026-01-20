from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    limit: int | None = None
