# mcp_client.py
# Starts the ClinicMate MCP server as a child process and talks to it over stdio: list tools, call tools.

import asyncio
import json
import os
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

from config.settings import MCP_SERVER_PYTHON, MCP_SERVER_SCRIPT

# Env vars the MCP server reads (clinicmate_mcp_server/config/settings.py).
# Locally it also has its own .env; on Cloud Run they exist only in our env, so we pass them on.
MCP_SERVER_ENV_KEYS = ["GEMINI_API_KEY", "DATABASE_URL"]


class McpClient:
    """One long-lived connection to the MCP server, opened once when the backend starts."""

    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self.tools: list = []  # tool cards from the server: name, description, inputSchema
        self.exit_stack = AsyncExitStack()

    async def connect(self) -> None:
        """Start the server process, do the MCP handshake and fetch the tool list."""
        forwarded = {key: os.environ[key] for key in MCP_SERVER_ENV_KEYS if key in os.environ}
        # Trusted mode: the server takes the patient id from each call's _meta (sent by call_tool below)
        server = StdioServerParameters(
            command=MCP_SERVER_PYTHON,
            args=[MCP_SERVER_SCRIPT],
            env={**get_default_environment(), **forwarded, "TRUST_CLIENT_PATIENT_ID": "true"},
        )
        read_stream, write_stream = await self.exit_stack.enter_async_context(stdio_client(server))
        self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()

        result = await self.session.list_tools()
        self.tools = result.tools

    async def call_tool(self, name: str, arguments: dict, patient_id: int | None = None) -> dict:
        """Run one tool on the MCP server and return its JSON result as a dict.
        patient_id goes in _meta, a side channel the LLM never sees or fills."""
        meta = {"patient_id": patient_id} if patient_id is not None else None
        result = await self.session.call_tool(name, arguments, meta=meta)
        text = "".join(block.text for block in result.content if block.type == "text")

        if result.isError:
            return {"error": text}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"result": text}

    async def close(self) -> None:
        """Close the session and stop the server process."""
        await self.exit_stack.aclose()


async def try_client() -> None:
    """Quick manual test: list tools and run one search."""
    client = McpClient()
    await client.connect()
    try:
        print(f"{len(client.tools)} tools:", [tool.name for tool in client.tools])
        result = await client.call_tool("search_doctors", {"specialty": "Cardiologist", "city": "Karachi"})
        print(json.dumps(result, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(try_client())