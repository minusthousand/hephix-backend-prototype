"""MCP Client wrapper for connecting to MCP servers."""
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Raised when MCP client operations fail."""


class MCPClient:
    """Simple MCP client for calling remote MCP tools."""

    def __init__(self, base_url: str = "http://localhost:3000"):
        """Initialize MCP client.
        
        Args:
            base_url: Base URL of the MCP server
        """
        self.base_url = base_url.rstrip("/")

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> str:
        """Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            timeout: Request timeout in seconds
            
        Returns:
            Tool result as a string
            
        Raises:
            MCPClientError: If the request fails
        """
        if not tool_name:
            raise MCPClientError("Tool name cannot be empty.")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/rpc",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                result = response.json()
                if "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    raise MCPClientError(f"MCP server error: {error_msg}")

                if "result" in result:
                    content = result["result"].get("content", [])
                    if content and isinstance(content, list):
                        return content[0].get("text", "")
                    return json.dumps(result["result"])

                return json.dumps(result)

        except httpx.HTTPStatusError as exc:
            logger.error("MCP request failed with status %s: %s", exc.response.status_code, exc)
            raise MCPClientError(
                f"MCP request failed with status {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            logger.error("MCP connection failed: %s", exc)
            raise MCPClientError(f"Failed to connect to MCP server: {exc}") from exc
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Invalid MCP response format: %s", exc)
            raise MCPClientError(f"Invalid MCP response format: {exc}") from exc


async def get_mcp_client() -> MCPClient:
    """Get an MCP client instance."""
    return MCPClient()
