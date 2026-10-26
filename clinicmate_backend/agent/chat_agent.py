# chat_agent.py
# The agent loop: user message -> LLM -> tool calls on MCP -> results back to LLM -> repeat until text.

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from agent.system_prompt import build_system_prompt
from config.settings import MAX_TOOL_ROUNDS
from llm.gemini_client import GeminiClient
from llm.llm_client import LlmClient
from mcp_connection.mcp_client import McpClient
from tool_retrieval.tool_index import ToolIndex
from tool_retrieval.tool_selector import select_tool_names

logger = logging.getLogger("chat_agent")

MAX_HISTORY_MESSAGES = 30
TOO_MANY_ROUNDS_REPLY = "Sorry, this is taking too long. Please ask again in a simpler way."

# Tools the LLM never sees here: chat login is for single-user clients (Claude Desktop; app users
# log in inside the app); chat history and background job tools are called only by the backend.
HIDDEN_TOOLS = {
    "login", "register", "logout",
    "save_conversation_turn", "get_conversation_history",
    "run_scheduled_jobs", "mark_reminders_sent", "get_doctors_needing_review_summary", "save_review_summary",
    "save_device_token", "remove_device_token", "get_device_tokens", "remove_dead_device_tokens",
}


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)  # every tool call of this turn, with its result


class ChatAgent:

    def __init__(self, llm: LlmClient, mcp: McpClient, tool_index: ToolIndex | None = None) -> None:
        self.llm = llm
        self.mcp = mcp
        self.tool_index = tool_index  # None = always send all tools
        self.last_turn_tools: dict[tuple[int | None, str], set[str]] = {}  # tools used in each chat's previous turn
        # (patient_id, conversation_id) -> history. A memory cache: logged-in patients' chats are also saved
        # in the database and loaded back after a restart. The patient id in the key means nobody can
        # read another patient's chat by guessing a conversation id.
        self.conversations: dict[tuple[int | None, str], list[dict]] = {}

    @property
    def llm_tools(self) -> list:
        return [tool for tool in self.mcp.tools if tool.name not in HIDDEN_TOOLS]

    async def run_turn(self, conversation_id: str, user_text: str, patient_id: int | None = None) -> AgentResult:
        """Whole turn at once (POST /chat): runs the stream and returns only the final result."""
        async for event in self.run_turn_stream(conversation_id, user_text, patient_id):
            if event["type"] == "done":
                return event["result"]
        raise RuntimeError("agent stream ended without a result")

    async def run_turn_stream(self, conversation_id: str, user_text: str, patient_id: int | None = None) -> AsyncIterator[dict]:
        """The agent loop as a stream of events:
        {"type": "token", "text": ...}   a piece of the reply as the LLM writes it
        {"type": "status", "tool": ...}  a tool is running (app can show "Searching doctors...")
        {"type": "done", "result": AgentResult}  always the last event
        patient_id comes from the app login (None = not logged in) and is passed to every tool call."""
        history = await self.get_history(patient_id, conversation_id)
        turn_start = len(history)
        history.append({"role": "user", "text": user_text})
        system_prompt = build_system_prompt()
        tools = await self.tools_for_turn((patient_id, conversation_id), user_text)
        turn_tool_calls: list[dict] = []
        turn_text: list[str] = []

        try:
            for round_number in range(1, MAX_TOOL_ROUNDS + 1):
                reply = None
                async for piece in self.llm.generate_stream(system_prompt, history, tools):
                    if isinstance(piece, str):
                        turn_text.append(piece)
                        yield {"type": "token", "text": piece}
                    else:
                        reply = piece  # the full LlmReply always comes last
                history.append({"role": "assistant", "text": reply.text, "raw": reply.raw})

                # No tool calls = final answer for the user
                if not reply.tool_calls:
                    self.trim_history(history)
                    self.last_turn_tools[(patient_id, conversation_id)] = {call["name"] for call in turn_tool_calls}
                    final_text = "".join(turn_text)
                    await self.save_turn(patient_id, conversation_id, user_text, final_text)
                    yield {"type": "done", "result": AgentResult(text=final_text, tool_calls=turn_tool_calls)}
                    return

                # Run every requested tool on the MCP server, then send all results back to the LLM
                results = []
                for call in reply.tool_calls:
                    logger.info("round %s: %s %s", round_number, call.name, call.arguments)
                    yield {"type": "status", "tool": call.name}
                    result = await self.mcp.call_tool(call.name, call.arguments, patient_id)
                    results.append({"name": call.name, "result": result})
                    turn_tool_calls.append({"name": call.name, "arguments": call.arguments, "result": result})
                history.append({"role": "tool", "results": results})
        except Exception:
            # A failed turn must not leave half a conversation behind (user message without an answer)
            del history[turn_start:]
            raise

        # Safety limit reached (Task 3: max rounds)
        logger.warning("max tool rounds reached for conversation %s", conversation_id)
        history.append({"role": "assistant", "text": TOO_MANY_ROUNDS_REPLY})
        await self.save_turn(patient_id, conversation_id, user_text, TOO_MANY_ROUNDS_REPLY)
        yield {"type": "token", "text": TOO_MANY_ROUNDS_REPLY}
        yield {"type": "done", "result": AgentResult(text=TOO_MANY_ROUNDS_REPLY, tool_calls=turn_tool_calls)}

    async def tools_for_turn(self, key: tuple[int | None, str], user_text: str) -> list:
        """Tool retrieval: only the tools that fit this message (plus last turn's). Any problem -> all tools."""
        if self.tool_index is None:
            return self.llm_tools
        try:
            ranked = await self.tool_index.rank(user_text)
        except Exception as error:
            logger.warning("tool retrieval failed, sending all tools: %s", error)
            return self.llm_tools
        names, reason = select_tool_names(ranked, self.last_turn_tools.get(key, set()))
        logger.info("tools for this turn: %s of %s (%s)", len(names), len(self.llm_tools), reason)
        return [tool for tool in self.llm_tools if tool.name in names]

    async def get_history(self, patient_id: int | None, conversation_id: str) -> list[dict]:
        """History from the memory cache; on first use after a restart, load a logged-in patient's chat from the database."""
        key = (patient_id, conversation_id)
        if key not in self.conversations:
            history: list[dict] = []
            if patient_id is not None:
                saved = await self.mcp.call_tool("get_conversation_history", {"conversation_id": conversation_id}, patient_id)
                history = [{"role": message["role"], "text": message["content"]} for message in saved.get("messages", [])]
            self.conversations[key] = history
        return self.conversations[key]

    async def save_turn(self, patient_id: int | None, conversation_id: str, user_text: str, assistant_text: str) -> None:
        """Save the question and final answer for logged-in patients. A failed save must not break the chat."""
        if patient_id is None or not assistant_text:
            return
        result = await self.mcp.call_tool(
            "save_conversation_turn",
            {"conversation_id": conversation_id, "user_text": user_text, "assistant_text": assistant_text},
            patient_id,
        )
        if "error" in result:
            logger.warning("could not save chat turn: %s", result["error"])

    def trim_history(self, history: list[dict]) -> None:
        """Keep the last messages, always starting at a user message so tool calls and results stay together."""
        while len(history) > MAX_HISTORY_MESSAGES:
            history.pop(0)
            while history and history[0]["role"] != "user":
                history.pop(0)


TERMINAL_PATIENT_ID = 1  # terminal test chats as seed patient 1 (Ali Hassan)


async def chat_in_terminal() -> None:
    """Manual test: talk to the agent in the terminal. Type 'exit' to stop."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    mcp = McpClient()
    await mcp.connect()
    agent = ChatAgent(llm=GeminiClient(), mcp=mcp)
    try:
        while True:
            user_text = input("\nYou: ").strip()
            if user_text.lower() in ("exit", "quit"):
                break
            if user_text:
                print("\nClinicMate: ", end="", flush=True)
                async for event in agent.run_turn_stream("terminal", user_text, TERMINAL_PATIENT_ID):
                    if event["type"] == "token":
                        print(event["text"], end="", flush=True)
                print()
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(chat_in_terminal())