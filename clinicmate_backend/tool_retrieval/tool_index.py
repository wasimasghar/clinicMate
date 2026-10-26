# tool_index.py
# Embeds every tool card (name + description + parameter descriptions) once at startup,
# then ranks the tools by how close they are to the user's message.

import logging
import math

from llm.llm_client import LlmClient

logger = logging.getLogger("tool_index")


def tool_card_text(tool) -> str:
    """The text that describes a tool: what the LLM itself reads, so it is also what we search."""
    params = tool.inputSchema.get("properties", {})
    param_lines = [f"- {name}: {schema.get('description', '')}" for name, schema in params.items()]
    return f"{tool.name}\n{tool.description or ''}\nParameters:\n" + "\n".join(param_lines)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """1 = same meaning, 0 = unrelated (same idea as pgvector's cosine distance, but 1 - distance)."""
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


class ToolIndex:

    def __init__(self, llm: LlmClient, tools: list) -> None:
        self.llm = llm
        self.tools = tools
        self.vectors: dict[str, list[float]] = {}  # tool name -> embedding of its card

    async def build(self) -> None:
        vectors = await self.llm.embed([tool_card_text(tool) for tool in self.tools], "RETRIEVAL_DOCUMENT")
        self.vectors = {tool.name: vector for tool, vector in zip(self.tools, vectors)}
        logger.info("tool index built for %s tools", len(self.vectors))

    async def rank(self, message: str) -> list[tuple[str, float]]:
        """All tools, most similar to the message first: [(tool_name, similarity), ...]."""
        query = (await self.llm.embed([message], "RETRIEVAL_QUERY"))[0]
        scores = [(name, cosine_similarity(query, vector)) for name, vector in self.vectors.items()]
        return sorted(scores, key=lambda item: item[1], reverse=True)
