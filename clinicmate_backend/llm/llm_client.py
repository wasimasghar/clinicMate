# common interface
# llm_client.py
# Common shapes for any LLM (Gemini now, Claude later): tool calls, the reply and the client interface.

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

# History format used by the agent (same for every LLM):
#   {"role": "user", "text": "..."}
#   {"role": "assistant", "text": "...", "raw": <provider message>}
#   {"role": "tool", "results": [{"name": "search_doctors", "result": {...}}]}


@dataclass
class ToolCall:
    name: str
    arguments: dict
    call_id: str | None = None


@dataclass
class LlmReply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None  # the provider's own message, sent back unchanged in the next round


class LlmClient(Protocol):
    async def generate(self, system_prompt: str, history: list[dict], tools: list) -> LlmReply:
        """Send the conversation and the tool list, get back text and/or tool calls."""
        ...

    def generate_stream(self, system_prompt: str, history: list[dict], tools: list) -> AsyncIterator[str | LlmReply]:
        """Same as generate, but yields text pieces (str) as they arrive and the full LlmReply last."""
        ...

    async def embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Text -> vectors. task_type: "RETRIEVAL_DOCUMENT" for stored texts, "RETRIEVAL_QUERY" for questions."""
        ...