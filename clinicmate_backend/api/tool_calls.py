# tool_calls.py
# Calls an MCP tool for a screen API and turns its {"error": ...} into the right HTTP status for the app.

from fastapi import HTTPException, Request


def status_for(message: str) -> int:
    """Map the tool's error message to an HTTP status the app can act on."""
    text = message.lower()
    if "log in" in text:
        return 401  # app: show the sign in screen
    if "not found" in text or "no upcoming" in text or "no active" in text:
        return 404
    if "no longer available" in text or "already" in text:
        return 409  # conflict: someone else took it, or it exists already
    return 400


async def call_tool(request: Request, name: str, arguments: dict, patient_id: int | None = None) -> dict:
    """Run an MCP tool (no LLM involved). Tool errors become HTTPException with a readable message."""
    result = await request.app.state.mcp.call_tool(name, arguments, patient_id)
    if "error" in result:
        raise HTTPException(status_code=status_for(result["error"]), detail=result["error"])
    return result


def without_none(**arguments) -> dict:
    """Drop arguments the app did not send, so the tool uses its own defaults."""
    return {key: value for key, value in arguments.items() if value is not None}
