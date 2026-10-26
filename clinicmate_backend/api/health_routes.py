# health_routes.py
# GET /health: quick check that the backend is up and connected to the MCP server.

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    tools = request.app.state.mcp.tools
    return {"status": "ok", "mcp_tools": len(tools)}