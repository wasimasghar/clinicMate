# tool_selector.py
# Picks the tools the LLM gets for one message: families of the top 5 matches + always-on families
# + families used in the last turn, or all tools when the match is weak. Fewer tools = fewer tokens and fewer wrong tool choices.

# Tools that work together go together: if one is picked, its whole family comes along,
# so a flow like slots -> quote -> book never misses a step inside one turn.
TOOL_FAMILIES = {
    "doctors": ["list_specialties", "list_cities", "search_doctors", "get_doctor_profile", "get_doctor_reviews"],
    "booking": ["get_available_slots", "quote_appointment", "book_appointment", "cancel_appointment",
                "reschedule_appointment", "get_my_appointments"],
    "waiting_list": ["join_waiting_list", "get_my_waiting_list", "leave_waiting_list"],
    "account": ["get_my_profile", "update_my_profile", "add_review"],
    "knowledge": ["search_policies", "search_health_guides"],
}
FAMILY_OF = {tool: family for family, tools in TOOL_FAMILIES.items() for tool in tools}

# Any message can be a policy or health question, and these are only 2 tools, so they are always sent
ALWAYS_ON_FAMILIES = {"knowledge"}
TOP_K = 5
MIN_SIMILARITY = 0.55  # best match below this = we are not sure what the user wants -> send all tools (tuned by evals)


def select_tool_names(ranked: list[tuple[str, float]], previous_tool_names: set[str]) -> tuple[set[str], str]:
    """Returns (tool names to send, short reason for the log)."""
    all_names = {name for name, _ in ranked}
    if not ranked or ranked[0][1] < MIN_SIMILARITY:
        return all_names, "weak match -> all tools"

    families = {FAMILY_OF[name] for name, _ in ranked[:TOP_K] if name in FAMILY_OF} | ALWAYS_ON_FAMILIES
    families |= {FAMILY_OF[name] for name in previous_tool_names if name in FAMILY_OF}
    selected = {tool for family in families for tool in TOOL_FAMILIES[family]} & all_names
    return selected, "families: " + ", ".join(sorted(families))
