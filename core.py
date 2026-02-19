"""
MCP Runtime + LangChain Agent core for Hephix backend.

Provides two independent runtimes:
  - DEPO_RUNTIME  → Depo MCP server  (default, always available)
  - DAREL_RUNTIME → Darel MCP server (separate, may have Cloudflare issues on EC2)

Each runtime spawns its own MCP server subprocess and exposes
a `chat_once` helper that drives a Claude agent with those tools.
"""

import asyncio
import os
import sys
from pathlib import Path
from contextlib import AsyncExitStack
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ── MCP server entry-points ──────────────────────────────────────

DEPO_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "mcp_server.py")],
)

DAREL_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "mcp_darel_server.py")],
)

EBAY_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "mcp_ebay_server.py")],
)
# ── System prompts ───────────────────────────────────────────────

DEPO_SYSTEM_PROMPT = (
    "You are Hephix — a helpful, friendly shopping assistant for online.depo.lv, "
    "a Latvian home-improvement and DIY store.\n\n"
    "When the user asks about products, use the `search_products` tool to look them up.\n"
    "Reply concisely; include product names, prices, and availability when available.\n"
    "If a search returns no results, say so and suggest alternative queries.\n"
    "When not asked about products, just be a helpful conversational assistant."
)

DAREL_SYSTEM_PROMPT = (
    "You are Hephix — a helpful, friendly shopping assistant for darel.lv, "
    "a Latvian building-materials and tools store.\n\n"
    "When the user asks about products, use the `darel_search` tool to look them up.\n"
    "Reply concisely; include product names, prices, and URLs when available.\n"
    "If a search returns no results, say so and suggest alternative queries.\n"
    "When not asked about products, just be a helpful conversational assistant."
)

EBAY_SYSTEM_PROMPT = (
    "You are Hephix — a helpful, friendly shopping assistant for eBay.\n\n"
    "When the user asks about products, use the `ebay_search` tool to look them up.\n"
    "Reply concisely; include product titles, prices, and item URLs when available.\n"
    "If a search returns no results, say so and suggest alternative queries.\n"
    "When not asked about products, just be a helpful conversational assistant."
)

# ── Generic MCP Runtime ──────────────────────────────────────────

class MCPRuntime:
    """Manages a single MCP server subprocess and exposes its tools."""

    def __init__(self, name: str, server_params: StdioServerParameters) -> None:
        self.name = name
        self._server_params = server_params
        self._stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._tools = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._tools is not None:
            return

        print(f"\n🚀 [CORE] Starting MCP Runtime ({self.name})...")
        stack = AsyncExitStack()

        errlog = sys.stderr
        errlog_path = os.getenv("MCP_ERRLOG_PATH")
        if errlog_path:
            errlog = stack.enter_context(
                open(errlog_path, "a", encoding="utf-8", buffering=1)
            )

        read, write = await stack.enter_async_context(
            stdio_client(self._server_params, errlog=errlog)
        )
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools = await load_mcp_tools(session)
        print(f"✅ [CORE] {self.name}: loaded {len(tools)} tool(s): {[t.name for t in tools]}")

        self._stack = stack
        self._session = session
        self._tools = tools
        print(f"🎉 [CORE] {self.name} runtime ready\n")

    async def aclose(self) -> None:
        print(f"\n🛑 [CORE] Shutting down {self.name}...")
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None
        self._tools = None
        print(f"👋 [CORE] {self.name} closed.\n")

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def tools(self):
        return self._tools


# ── Singleton runtimes ───────────────────────────────────────────

DEPO_RUNTIME = MCPRuntime("depo", DEPO_SERVER_PARAMS)
DAREL_RUNTIME = MCPRuntime("darel", DAREL_SERVER_PARAMS)
EBAY_RUNTIME = MCPRuntime("ebay", EBAY_SERVER_PARAMS)


# ── History helpers ──────────────────────────────────────────────

def new_depo_history() -> List[BaseMessage]:
    return [SystemMessage(content=DEPO_SYSTEM_PROMPT)]


def new_darel_history() -> List[BaseMessage]:
    return [SystemMessage(content=DAREL_SYSTEM_PROMPT)]

def new_ebay_history() -> List[BaseMessage]:
    return [SystemMessage(content=EBAY_SYSTEM_PROMPT)]


# ── Agent chat functions ─────────────────────────────────────────

async def _chat_once(
    runtime: MCPRuntime,
    system_prompt: str,
    history: List[BaseMessage],
    user_text: str,
) -> List[BaseMessage]:
    """Run one turn through the agent backed by `runtime`."""
    await runtime.start()

    async with runtime.lock:
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        model = ChatAnthropic(model=model_name)
        agent = create_agent(model, runtime.tools, system_prompt=system_prompt)

        result = await agent.ainvoke(
            {"messages": [*history, HumanMessage(content=user_text)]}
        )
        return result["messages"]


async def chat_depo(history: List[BaseMessage], user_text: str) -> List[BaseMessage]:
    """Depo agent — default chat endpoint."""
    return await _chat_once(DEPO_RUNTIME, DEPO_SYSTEM_PROMPT, history, user_text)


async def chat_darel(history: List[BaseMessage], user_text: str) -> List[BaseMessage]:
    """Darel agent — separate chat endpoint."""
    return await _chat_once(DAREL_RUNTIME, DAREL_SYSTEM_PROMPT, history, user_text)


async def chat_ebay(history: List[BaseMessage], user_text: str) -> List[BaseMessage]:
    """eBay agent — separate chat endpoint."""
    return await _chat_once(EBAY_RUNTIME, EBAY_SYSTEM_PROMPT, history, user_text)
