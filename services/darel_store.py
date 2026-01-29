from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("darel")

DAREL_SEARCH_URL = "https://darel.lv/en/module/iqitsearch/searchiqit"
DAREL_BASE_URL = "https://darel.lv/"


@mcp.tool()
def darel_search(query: str, results_per_page: int = 10) -> list[dict[str, Any]]:
    """Search darel.lv and return a compact list of products.

    Args:
        query: Search query string.
        results_per_page: Max results to return.
    Returns:
        List of compact product dicts.
    """
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
            return []
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
