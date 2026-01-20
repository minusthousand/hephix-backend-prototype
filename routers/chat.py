from fastapi import APIRouter

from schemas import ChatRequest
from services.depo_store import search_products

router = APIRouter()

@router.options("/chat")
async def chat_options():
    return {}

@router.post("/chat")
async def chat(payload: ChatRequest):
    limit = payload.limit if payload.limit is not None else 10
    results = await search_products(payload.message, limit=limit)
    return {"message": results}
