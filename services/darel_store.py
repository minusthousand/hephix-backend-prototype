import logging
import time
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("darel")
logger = logging.getLogger(__name__)

DAREL_SEARCH_URL = "https://darel.lv/en/module/iqitsearch/searchiqit"
DAREL_BASE_URL = "https://darel.lv/"
DAREL_COOKIE_TTL_SECONDS = 30 * 60
_darel_cookie_cache: dict[str, Any] = {"expires_at": 0, "cookies": None}


def _get_darel_cookies() -> list[dict[str, Any]] | None:
    now = time.time()
    cached = _darel_cookie_cache.get("cookies")
    expires_at = _darel_cookie_cache.get("expires_at", 0)
    if cached and expires_at > now:
        return cached

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(DAREL_BASE_URL, wait_until="domcontentloaded", timeout=15000)
            cookies = context.cookies()
            context.close()
            browser.close()
    except Exception:
        return None

    if not cookies:
        return None

    _darel_cookie_cache["cookies"] = cookies
    _darel_cookie_cache["expires_at"] = now + DAREL_COOKIE_TTL_SECONDS
    return cookies


@mcp.tool()
def darel_search(query: str, results_per_page: int = 10) -> list[dict[str, Any]]:
    """Search darel.lv and return a compact list of products.

    Args:
        query: Search query string.
        results_per_page: Max results to return.
    Returns:
        List of compact product dicts.
    """
    results, _ = _darel_search_with_error(query, results_per_page)
    return results


def _darel_search_with_error(query: str, results_per_page: int = 10) -> tuple[list[dict[str, Any]], str | None]:
    """Search darel.lv and return (results, error_message)."""
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
        "origin": "https://darel.lv",
        "referer": "https://darel.lv/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "accept-language": "en-US,en;q=0.9",
    }

    data = {"s": query, "resultsPerPage": str(results_per_page), "ajax": "true"}

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        cookies = _get_darel_cookies()
        if cookies:
            for c in cookies:
                name = c.get("name")
                value = c.get("value")
                if not name:
                    continue
                client.cookies.set(
                    name,
                    value,
                    domain=c.get("domain"),
                    path=c.get("path") or "/",
                )
        # Prime session cookies from homepage to avoid 403s.
        client.get(
            DAREL_BASE_URL,
            headers={
                "user-agent": headers["user-agent"],
                "accept-language": headers["accept-language"],
            },
        )
        r = client.post(DAREL_SEARCH_URL, headers=headers, data=data)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            # Darel frequently blocks bot-like requests; avoid crashing the API.
            return [], f"Darel search failed with HTTP {r.status_code}."
        payload = r.json()
        logger.info("Darel search raw response: %s", payload)
        products = payload.get("products", [])

    compact: list[dict[str, Any]] = []
    for p in products:
        if not isinstance(p, dict):
            continue
        cover = p.get("cover") or {}
        by_size = cover.get("bySize") or {}
        thumb = (
            by_size.get("home_default", {}).get("url")
            or by_size.get("medium_default", {}).get("url")
            or by_size.get("small_default", {}).get("url")
            or cover.get("medium", {}).get("url")
            or cover.get("small", {}).get("url")
            or cover.get("large", {}).get("url")
        )
        compact.append(
            {
                "id_product": p.get("id_product"),
                "name": p.get("name"),
                "price": p.get("price"),
                "url": p.get("url") or p.get("link"),
                "reference": p.get("reference"),
                "manufacturer_name": p.get("manufacturer_name"),
                "category_name": p.get("category_name"),
                "thumbnail": thumb,
            }
        )
    return compact, None


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
