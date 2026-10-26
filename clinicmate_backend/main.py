# main.py
# FastAPI app: connects to the MCP server on startup, creates the agent and registers the routes.

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent.chat_agent import ChatAgent
from api import (
    appointment_routes, auth_routes, chat_routes, device_routes, doctor_routes,
    health_routes, job_routes, profile_routes, waiting_list_routes,
)
from llm.gemini_client import GeminiClient
from mcp_connection.mcp_client import McpClient
from tool_retrieval.tool_index import ToolIndex

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: one MCP connection and one agent for the whole app
    mcp = McpClient()
    await mcp.connect()
    app.state.mcp = mcp
    llm = GeminiClient()
    agent = ChatAgent(llm=llm, mcp=mcp)
    # Tool retrieval: embed the tool cards once. If that fails, the agent simply sends all tools.
    try:
        agent.tool_index = ToolIndex(llm, agent.llm_tools)
        await agent.tool_index.build()
    except Exception as error:
        agent.tool_index = None
        logging.warning("tool index not built, using all tools: %s", error)
    app.state.agent = agent
    logging.info("Connected to MCP server with %s tools", len(mcp.tools))

    yield  # the app runs here

    # Shutdown: stop the MCP server process
    await mcp.close()


app = FastAPI(title="ClinicMate Backend", lifespan=lifespan)
app.include_router(health_routes.router)
app.include_router(chat_routes.router)
app.include_router(job_routes.router)
app.include_router(device_routes.router)
app.include_router(auth_routes.router)
app.include_router(doctor_routes.router)
app.include_router(appointment_routes.router)
app.include_router(waiting_list_routes.router)
app.include_router(profile_routes.router)
