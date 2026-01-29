#!/usr/bin/env python3
"""MCP Server entrypoint for Darel store."""
import sys

from services.darel_store import mcp


def main():
    print("Starting MCP Server (darel)...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
