from fastapi import APIRouter

from schemas import ChatRequest
from services.depo_store import search_products
from services.depo_store import search_products_structured
from services.darel_store import _darel_search_with_error
from services.darel_store import darel_search

router = APIRouter()

@router.options("/chat")
async def chat_options():
    return {}

@router.post("/chat")
async def chat(payload: ChatRequest):
    """Return combined results from Depo and Darel as JSON array."""
    limit = payload.limit if payload.limit is not None else 10

    from asyncio import get_running_loop
    loop = get_running_loop()

    # gather depo structured results (async) and darel (sync -> executor)
    depo_results = await search_products_structured(payload.message, limit=limit)

    def _call_darel():
        return _darel_search_with_error(payload.message, results_per_page=limit)

    darel_results, darel_error = await loop.run_in_executor(None, _call_darel)

    results: list[dict[str, str | None]] = []

    for p in depo_results[:limit]:
        name = p.get("name") or "Unknown"
        price = p.get("price") or "N/A"
        unit = p.get("unit") or ""
        price_text = f"{price} {unit}".strip()
        thumb = p.get("thumbnail") or None
        results.append(
            {"title": name, "price": price_text, "thumbnail": thumb, "source": "depo"}
        )

    for p in darel_results[:limit]:
        name = p.get("name") or "Unknown"
        price = p.get("price") or "N/A"
        thumb = p.get("thumbnail") or None
        results.append(
            {
                "title": name,
                "price": price,
                "thumbnail": thumb,
                "source": "darel",
                "url": p.get("url") or None,
            }
        )

    return {"results": results}


@router.post("/darel")
async def darel(payload: ChatRequest):
    """Search Darel store and return compact product list as text."""
    limit = payload.limit if payload.limit is not None else 10
    # darel_search is synchronous (mcp tool defined as sync), call in threadpool
    from asyncio import get_running_loop
    loop = get_running_loop()

    def _call():
        return darel_search(payload.message, results_per_page=limit)

    results = await loop.run_in_executor(None, _call)
    # format compact results into a simple text
    if not results:
        return {"message": "No products found."}

    lines = ["Darel search results:", ""]
    for i, p in enumerate(results[:limit], 1):
        name = p.get("name") or "Unknown"
        price = p.get("price") or "N/A"
        url = p.get("url") or ""
        lines.append(f"{i}. {name}")
        lines.append(f"   Price: {price}")
        if url:
            lines.append(f"   URL: {url}")
        if i != min(limit, len(results)):
            lines.append("")

    return {"message": "\n".join(lines)}


@router.get("/darel")
async def darel_get(q: str, limit: int | None = None):
    """GET endpoint to search Darel and return JSON results.

    Query params:
    - q: search query (required)
    - limit: maximum results to return (optional)
    """
    max_results = limit if limit is not None else 10
    from asyncio import get_running_loop
    loop = get_running_loop()

    def _call():
        return darel_search(q, results_per_page=max_results)

    results = await loop.run_in_executor(None, _call)
    if not results:
        return {"results": []}

    # trim to requested limit and return raw compact objects
    return {"results": results[:max_results]}


@router.get("/search")
async def unified_search(q: str, source: str | None = None, limit: int | None = None):
    """Unified search endpoint. `source` can be 'depo', 'darel', or omitted for both.

    Returns JSON: {"results": [{...}], "sources": ["depo","darel"]}
    """
    max_results = limit if limit is not None else 10
    src = (source or "both").lower()
    results = {}

    from asyncio import get_running_loop
    loop = get_running_loop()

    async def _call_depo():
        return await search_products_structured(q, limit=max_results)

    def _call_darel():
        return darel_search(q, results_per_page=max_results)

    if src in ("depo", "both"):
        depo_res = await _call_depo()
        results["depo"] = depo_res
    if src in ("darel", "both"):
        # darel_search is sync; run in executor
        dar_res = await loop.run_in_executor(None, _call_darel)
        results["darel"] = dar_res

    # Normalize to arrays and return
    combined = []
    if src == "depo":
        combined = results.get("depo", [])
    elif src == "darel":
        combined = results.get("darel", [])
    else:
        # both: tag entries with source
        for item in results.get("depo", []):
            it = dict(item)
            it["source"] = "depo"
            combined.append(it)
        for item in results.get("darel", []):
            it = dict(item)
            it["source"] = "darel"
            combined.append(it)

    return {"results": combined}
