# chat_routes.py
# POST /chat returns the whole reply at once; POST /chat/stream sends it piece by piece (SSE).

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from google.genai import errors as gemini_errors

from agent.response_builder import build_chat_response
from api.auth import get_patient_id
from schemas.chat_schemas import ChatRequest, ChatResponse
from streaming.sse_events import done_event, error_event, status_event, token_event

logger = logging.getLogger("chat_routes")
router = APIRouter()

BUSY_MESSAGE = "The assistant is busy right now. Please try again in a minute."


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request, patient_id: int | None = Depends(get_patient_id)) -> ChatResponse:
    agent = request.app.state.agent
    try:
        result = await agent.run_turn(body.conversation_id, body.message, patient_id)
    except gemini_errors.APIError as error:
        logger.error("Gemini error: %s", error)
        raise HTTPException(status_code=503, detail=BUSY_MESSAGE)
    return build_chat_response(body.conversation_id, result)


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request, patient_id: int | None = Depends(get_patient_id)) -> StreamingResponse:
    """Events: token (reply text pieces), status (a tool is running), done (full ChatResponse), error."""
    agent = request.app.state.agent

    async def events() -> AsyncIterator[str]:
        try:
            async for event in agent.run_turn_stream(body.conversation_id, body.message, patient_id):
                if event["type"] == "token":
                    yield token_event(event["text"])
                elif event["type"] == "status":
                    yield status_event(event["tool"])
                elif event["type"] == "done":
                    response = build_chat_response(body.conversation_id, event["result"])
                    yield done_event(response.model_dump())
        except gemini_errors.APIError as error:
            logger.error("Gemini error: %s", error)
            yield error_event(BUSY_MESSAGE)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # no caching or proxy buffering
    )
