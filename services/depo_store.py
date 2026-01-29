import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from services.graphql_service import GraphQLRequestError, execute_graphql_request

mcp = FastMCP("depo-store")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEPO_GRAPHQL_ENDPOINT = "https://online.depo.lv/graphql"

DEPO_PRODUCTS_QUERY = """
query products($searchString: String, $order: [ProductSortModelInput], $facets: [FacetFilterInput], $categoryId: Int, $rows: Int, $start: Int) {
  products(
    searchString: $searchString
    categoryId: $categoryId
    order_by: $order
    facets: $facets
    rows: $rows
    start: $start
  ) {
    pageInfo {
      endCursor
      startCursor
      hasPreviousPage
      hasNextPage
      totalCount
      __typename
    }
    edges {
      node {
        id
        name
        thumbnailPictureUrl
        primaryBarcode
        cardThumbnailPictureUrl
        energyEfficiency
        energyEfficiencyDocumentUrl
        energyEfficiencyImageUrl
        unitConversion {
          factor
          fromUnit
          toUnit
          __typename
        }
        stockItems {
          locationId
          locationAddress
          quantity
          __typename
        }
        prices {
          id
          priceType
          yellow {
            priceWithVat
            unit
            __typename
          }
          orange {
            priceWithVat
            unit
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
""".strip()


def _pick_price(prices: Any) -> tuple[str, str | None]:
    if not prices:
        return "Price not available", None

    if isinstance(prices, dict):
        price_items = [prices]
    elif isinstance(prices, list):
        price_items = prices
    else:
        return "Price not available", None

    for price_item in price_items:
        if not isinstance(price_item, dict):
            continue
        yellow = price_item.get("yellow") or {}
        price_with_vat = yellow.get("priceWithVat")
        unit = yellow.get("unit")
        if price_with_vat is not None:
            return f"€{price_with_vat}", unit

    for price_item in price_items:
        if not isinstance(price_item, dict):
            continue
        orange = price_item.get("orange") or {}
        price_with_vat = orange.get("priceWithVat")
        unit = orange.get("unit")
        if price_with_vat is not None:
            return f"€{price_with_vat}", unit

    return "Price not available", None


def _summarize_stock(stock_items: list[dict[str, Any]] | None) -> str | None:
    if not stock_items:
        return None

    total = 0
    for item in stock_items:
        qty = item.get("quantity")
        if isinstance(qty, (int, float)):
            total += qty

    if total <= 0:
        return "Out of stock"
    return f"In stock ({int(total)} total)"


def _format_products(payload: dict[str, Any], limit: int) -> str:
    products_data = payload.get("data", {}).get("products", {})
    edges = products_data.get("edges", []) or []
    page_info = products_data.get("pageInfo", {}) or {}

    if not edges:
        return "No products found."

    lines = ["Search results from online.depo.lv:", ""]
    for index, edge in enumerate(edges[:limit], 1):
        node = edge.get("node", {}) or {}
        name = node.get("name") or "Unknown Product"
        price, unit = _pick_price(node.get("prices"))
        availability = _summarize_stock(node.get("stockItems"))
        thumbnail = node.get("thumbnailPictureUrl") or node.get("cardThumbnailPictureUrl")

        lines.append(f"{index}. {name}")
        lines.append(f"   Price: {price}{f' / {unit}' if unit else ''}")
        if availability:
            lines.append(f"   Availability: {availability}")
        if node.get("primaryBarcode"):
            lines.append(f"   Barcode: {node['primaryBarcode']}")
        if thumbnail:
            lines.append(f"   Image: {thumbnail}")
        if index != min(limit, len(edges)):
            lines.append("")

    total_count = page_info.get("totalCount")
    if isinstance(total_count, int) and total_count > limit:
        lines.extend(["", f"(Showing {limit} results out of {total_count}.)"])

    return "\n".join(lines).strip()


def products_compact_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact list of product dicts from a GraphQL payload.

    Each item will contain: id, name, price, unit, availability, thumbnail, barcode
    """
    products_data = payload.get("data", {}).get("products", {})
    edges = products_data.get("edges", []) or []

    compact: list[dict[str, Any]] = []
    for edge in edges:
        node = (edge or {}).get("node", {}) or {}
        price, unit = _pick_price(node.get("prices"))
        availability = _summarize_stock(node.get("stockItems"))
        thumbnail = node.get("thumbnailPictureUrl") or node.get("cardThumbnailPictureUrl")

        compact.append(
            {
                "id": node.get("id"),
                "name": node.get("name"),
                "price": price,
                "unit": unit,
                "availability": availability,
                "thumbnail": thumbnail,
                "barcode": node.get("primaryBarcode"),
            }
        )

    return compact


@mcp.tool()
async def search_products(query: str, limit: int = 10) -> str:
    """Search for products on online.depo.lv via GraphQL."""
    if not query or not query.strip():
        return "Error: Search query cannot be empty."

    limit = min(max(1, limit), 50)

    variables = {
        "start": 0,
        "rows": limit,
        "searchString": query.strip(),
    }

    try:
        payload = await execute_graphql_request(
            DEPO_GRAPHQL_ENDPOINT,
            DEPO_PRODUCTS_QUERY,
            variables=variables,
        )
    except GraphQLRequestError as exc:
        logger.error("GraphQL search failed: %s", exc)
        return "Error: Unable to search online.depo.lv at the moment."

    return _format_products(payload, limit)


async def search_products_structured(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search and return structured product list suitable for JSON API."""
    if not query or not query.strip():
        return []

    limit = min(max(1, limit), 50)

    variables = {
        "start": 0,
        "rows": limit,
        "searchString": query.strip(),
    }

    try:
        payload = await execute_graphql_request(
            DEPO_GRAPHQL_ENDPOINT,
            DEPO_PRODUCTS_QUERY,
            variables=variables,
        )
    except GraphQLRequestError as exc:
        logger.error("GraphQL search failed: %s", exc)
        return []

    return products_compact_from_payload(payload)[:limit]


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
