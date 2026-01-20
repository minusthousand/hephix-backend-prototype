import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GraphQLRequestError(RuntimeError):
    """Raised when a GraphQL request fails or returns errors."""


async def execute_graphql_request(
    endpoint: str,
    query: str,
    variables: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Send a GraphQL request and return the JSON payload.

    Raises GraphQLRequestError when the server returns GraphQL errors or
    when the request fails.
    """
    if not endpoint or not endpoint.strip():
        raise GraphQLRequestError("GraphQL endpoint cannot be empty.")
    if not query or not query.strip():
        raise GraphQLRequestError("GraphQL query cannot be empty.")

    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables

    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        request_headers.update(headers)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(endpoint, json=payload, headers=request_headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("GraphQL request failed with status %s: %s", exc.response.status_code, exc)
            raise GraphQLRequestError(
                f"GraphQL request failed with status {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            logger.error("GraphQL request error: %s", exc)
            raise GraphQLRequestError("GraphQL request failed due to a network error.") from exc

    try:
        data = response.json()
    except ValueError as exc:
        logger.error("GraphQL response was not valid JSON.")
        raise GraphQLRequestError("GraphQL response was not valid JSON.") from exc

    if "errors" in data:
        logger.error("GraphQL response contained errors: %s", data["errors"])
        raise GraphQLRequestError("GraphQL response contained errors.")

    return data
