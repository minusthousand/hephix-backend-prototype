import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("darel")

DAREL_SEARCH_URL = "https://darel.lv/en/module/iqitsearch/searchiqit"


@mcp.tool()
def darel_search(query: str, results_per_page: int = 10, cookie: Optional[str] = None) -> list[dict[str, Any]]:
    """Search darel.lv and return a compact list of products.

    Args:
        query: Search query string.
        results_per_page: Max results to return.
        cookie: Optional cookie string to bypass Cloudflare if needed.
    Returns:
        List of compact product dicts.
    """
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
        "origin": "https://darel.lv",
        "referer": "https://darel.lv/",
    }

    cookie = cookie or os.getenv("DAREL_COOKIE")
    if cookie:
        headers["cookie"] = cookie

    data = {"s": query, "resultsPerPage": str(results_per_page), "ajax": "true"}

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.post(DAREL_SEARCH_URL, headers=headers, data=data)
        r.raise_for_status()
        products = r.json().get("products", [])

    compact: list[dict[str, Any]] = []
    for p in products:
        if not isinstance(p, dict):
            continue
        compact.append(
            {
                "id_product": p.get("id_product"),
                "name": p.get("name"),
                "price": p.get("price"),
                "url": p.get("url") or p.get("link"),
                "reference": p.get("reference"),
                "manufacturer_name": p.get("manufacturer_name"),
                "category_name": p.get("category_name"),
            }
        )
    return compact


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
