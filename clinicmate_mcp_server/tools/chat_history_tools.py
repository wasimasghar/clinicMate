# chat_history_tools.py
# Internal MCP tools used by the ClinicMate backend to save and load chat history. Hidden from the LLM.

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import chat_repository
from services import session_service
from services.session_service import NotLoggedInError


def register_chat_history_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def save_conversation_turn(
        conversation_id: Annotated[str, Field(min_length=1, max_length=100)],
        user_text: Annotated[str, Field(min_length=1, max_length=2000)],
        assistant_text: Annotated[str, Field(max_length=10000)],
    ) -> dict:
        """INTERNAL (backend only): save one question and answer of the logged-in patient's chat."""
        try:
            patient_id = session_service.current_patient_id()
        except NotLoggedInError as error:
            return {"error": str(error)}
        chat_repository.save_turn(patient_id, conversation_id, user_text, assistant_text)
        return {"saved": True}

    @mcp.tool()
    def get_conversation_history(
        conversation_id: Annotated[str, Field(min_length=1, max_length=100)],
        limit: Annotated[int, Field(ge=1, le=30)] = 20,
    ) -> dict:
        """INTERNAL (backend only): latest messages of the logged-in patient's chat, oldest first."""
        try:
            patient_id = session_service.current_patient_id()
        except NotLoggedInError as error:
            return {"error": str(error)}
        return {"messages": chat_repository.get_recent_messages(patient_id, conversation_id, limit)}
