import base64
import logging
import os
import time
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ebay")
logger = logging.getLogger(__name__)

EBAY_ENV = os.getenv("EBAY_ENV", "production").strip().lower()
EBAY_API_BASE = os.getenv(
    "EBAY_API_BASE",
    "https://api.sandbox.ebay.com" if EBAY_ENV == "sandbox" else "https://api.ebay.com",
).rstrip("/")
EBAY_OAUTH_URL = os.getenv(
    "EBAY_OAUTH_URL",
    f"{EBAY_API_BASE}/identity/v1/oauth2/token",
)
EBAY_SCOPE = os.getenv("EBAY_SCOPE", "https://api.ebay.com/oauth/api_scope")
EBAY_MARKETPLACE_ID = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US")
EBAY_ACCEPT_LANGUAGE = os.getenv("EBAY_ACCEPT_LANGUAGE", "").strip()
EBAY_ENDUSERCTX = os.getenv("EBAY_ENDUSERCTX", "").strip()

_token_cache: dict[str, Any] = {"expires_at": 0.0, "token": None}


def _get_basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _get_app_token() -> str | None:
    now = time.time()
    cached = _token_cache.get("token")
    expires_at = float(_token_cache.get("expires_at") or 0)
    if cached and expires_at - 30 > now:
        return cached

    client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
    client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {_get_basic_auth_header(client_id, client_secret)}",
    }
    data = {
        "grant_type": "client_credentials",
        "scope": EBAY_SCOPE,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(EBAY_OAUTH_URL, headers=headers, data=data)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.error("eBay OAuth token request failed: %s", exc)
        return None

    token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    if not token:
        return None

    ttl = float(expires_in) if isinstance(expires_in, (int, float)) else 0
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + max(ttl, 0)
    return token


def _compact_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        price = item.get("price") or {}
        shipping = item.get("shippingOptions") or []
        shipping_cost = None
        shipping_currency = None
        if shipping and isinstance(shipping, list):
            cost = (shipping[0] or {}).get("shippingCost") or {}
            shipping_cost = cost.get("value")
            shipping_currency = cost.get("currency")

        image = item.get("image") or {}
        image_url = image.get("imageUrl")
        if not image_url:
            additional = item.get("additionalImages") or []
            if additional and isinstance(additional, list):
                image_url = (additional[0] or {}).get("imageUrl")

        compact.append(
            {
                "item_id": item.get("itemId"),
                "title": item.get("title"),
                "price": price.get("value"),
                "currency": price.get("currency"),
                "item_web_url": item.get("itemWebUrl"),
                "condition": item.get("condition"),
                "seller_username": (item.get("seller") or {}).get("username"),
                "buying_options": item.get("buyingOptions"),
                "image_url": image_url,
                "shipping_cost": shipping_cost,
                "shipping_currency": shipping_currency,
            }
        )
    return compact


@mcp.tool()
def ebay_search(query: str, limit: int = 10, marketplace_id: str | None = None) -> list[dict[str, Any]]:
    """Search eBay items via the Browse API and return a compact list."""
    if not query or not query.strip():
        return [{"error": "Search query cannot be empty."}]

    token = _get_app_token()
    if not token:
        return [{"error": "Missing or invalid eBay credentials."}]

    limit = min(max(1, limit), 50)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": marketplace_id or EBAY_MARKETPLACE_ID,
    }
    if EBAY_ACCEPT_LANGUAGE:
        headers["Accept-Language"] = EBAY_ACCEPT_LANGUAGE
    if EBAY_ENDUSERCTX:
        headers["X-EBAY-C-ENDUSERCTX"] = EBAY_ENDUSERCTX

    params = {
        "q": query.strip(),
        "limit": str(limit),
    }

    url = f"{EBAY_API_BASE}/buy/browse/v1/item_summary/search"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.error("eBay search failed: %s", exc)
        return [{"error": "eBay search failed."}]

    items = payload.get("itemSummaries") or []
    if not items:
        return []
    return _compact_items(items)[:limit]


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
