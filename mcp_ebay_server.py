#!/usr/bin/env python3
"""MCP Server entrypoint for eBay store."""
import sys

from services.ebay_store import mcp


def main():
    print("Starting MCP Server (ebay)...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
