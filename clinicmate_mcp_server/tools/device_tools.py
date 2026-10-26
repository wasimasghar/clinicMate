# device_tools.py
# Backend-only MCP tools for FCM device tokens: the app registers its token through the backend,
# and the background agent reads tokens to send notifications. Hidden from the chat LLM.

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import device_token_repository
from services import session_service
from services.session_service import NotLoggedInError

BACKEND_ONLY_ERROR = {"error": "This tool is only for the ClinicMate backend."}
TOKEN = Annotated[str, Field(min_length=10, max_length=4096)]


def register_device_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def save_device_token(token: TOKEN, platform: Literal["android", "ios"]) -> dict:
        """BACKEND ONLY: remember the logged-in patient's phone for push notifications."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        try:
            device_token_repository.save_token(session_service.current_patient_id(), token, platform)
        except NotLoggedInError as error:
            return {"error": str(error)}
        return {"saved": True}

    @mcp.tool()
    def remove_device_token(token: TOKEN) -> dict:
        """BACKEND ONLY: the logged-in patient logged out on this phone."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        try:
            removed = device_token_repository.remove_patient_token(session_service.current_patient_id(), token)
        except NotLoggedInError as error:
            return {"error": str(error)}
        return {"removed": removed}

    @mcp.tool()
    def get_device_tokens(patient_ids: Annotated[list[int], Field(max_length=1000)]) -> dict:
        """BACKEND ONLY: phones of these patients, for sending notifications."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        return {"tokens": device_token_repository.get_tokens(patient_ids)}

    @mcp.tool()
    def remove_dead_device_tokens(tokens: Annotated[list[str], Field(max_length=1000)]) -> dict:
        """BACKEND ONLY: delete tokens that FCM reported as no longer valid."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        return {"removed": device_token_repository.remove_tokens(tokens)}
