#!/usr/bin/env python3
"""MCP Server entry point for Hephix backend.

This server exposes the product search functionality via MCP protocol.
Run with: python mcp_server.py
"""
import sys

from services.depo_store import mcp


def main():
    """Start the MCP server using stdio transport."""
    print("Starting MCP Server (depo-store)...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
