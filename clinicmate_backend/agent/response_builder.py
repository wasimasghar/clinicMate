# response_builder.py
# Builds the app response from the agent result: reply text + doctor cards + booking card (from tool data, not LLM text).

from agent.chat_agent import AgentResult
from schemas.chat_schemas import BookingCard, ChatResponse, DoctorCard, SourceInfo

# Tools whose results become a booking card, and the card kind for each
BOOKING_TOOLS = {
    "quote_appointment": ("quote", "quote"),
    "book_appointment": ("booked", "appointment"),
    "cancel_appointment": ("cancelled", "appointment"),
    "reschedule_appointment": ("rescheduled", "appointment"),
}

# Tools that answer health questions (RAG, step 4) -> show the health disclaimer
HEALTH_TOOLS = {"search_health_guides"}
# Tools whose results carry document sources (RAG)
KNOWLEDGE_TOOLS = {"search_policies", "search_health_guides"}

def build_doctor_cards(tool_calls: list[dict]) -> list[DoctorCard]:
    """Cards from the LAST search_doctors or get_doctor_profile call of this turn."""
    for call in reversed(tool_calls):
        result = call["result"]
        if "error" in result:
            continue
        if call["name"] == "search_doctors":
            return [DoctorCard(**doctor) for doctor in result.get("doctors", [])]
        if call["name"] == "get_doctor_profile":
            return [DoctorCard(**result)]
    return []


def build_booking_card(tool_calls: list[dict]) -> BookingCard | None:
    """Card from the LAST successful quote / book / cancel / reschedule call of this turn."""
    for call in reversed(tool_calls):
        if call["name"] not in BOOKING_TOOLS or "error" in call["result"]:
            continue
        kind, data_key = BOOKING_TOOLS[call["name"]]
        return BookingCard(kind=kind, **call["result"][data_key])
    return None


def build_sources(tool_calls: list[dict]) -> list[SourceInfo]:
    """Unique sources from every successful RAG search of this turn."""
    sources: list[SourceInfo] = []
    for call in tool_calls:
        if call["name"] not in KNOWLEDGE_TOOLS or not call["result"].get("found"):
            continue
        for source in call["result"]["sources"]:
            info = SourceInfo(**source)
            if info not in sources:
                sources.append(info)
    return sources


def build_chat_response(conversation_id: str, agent_result: AgentResult) -> ChatResponse:
    tool_names = {call["name"] for call in agent_result.tool_calls}
    return ChatResponse(
        conversation_id=conversation_id,
        reply=agent_result.text,
        doctor_cards=build_doctor_cards(agent_result.tool_calls),
        booking_card=build_booking_card(agent_result.tool_calls),
        sources=build_sources(agent_result.tool_calls),
        show_disclaimer=bool(tool_names & HEALTH_TOOLS),
    )