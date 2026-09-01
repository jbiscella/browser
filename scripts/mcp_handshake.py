"""Spawn the server over real stdio and list its tools.

This is the test that catches a stray print(): stdout is the JSON-RPC transport,
so any accidental write to it corrupts the stream and the server dies inside
Claude Code with an opaque parse error.
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "webresearch"])


async def main() -> None:
    async with stdio_client(PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"handshake OK -- {len(tools)} tools")
            for t in sorted(tools, key=lambda x: x.name):
                first_line = (t.description or "").strip().split("\n")[0]
                print(f"  {t.name:16s} {first_line[:60]}")

            # Exercise one tool over the wire, so we know dispatch works too.
            res = await session.call_tool("list_documents", {})
            assert not res.isError, res
            print("\ncall_tool(list_documents) OK")


if __name__ == "__main__":
    asyncio.run(main())
