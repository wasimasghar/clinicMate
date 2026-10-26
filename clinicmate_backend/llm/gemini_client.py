# gemini_client.py
# Gemini version of LlmClient: converts MCP tools and our history to Gemini format and back.

import asyncio
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from llm.llm_client import LlmReply, ToolCall

NO_ANSWER_TEXT = "Sorry, I could not answer that. Please try again."
EMBEDDING_MODEL = "gemini-embedding-001"  # same model and size as the MCP server's embeddings
EMBEDDING_DIMENSIONS = 768


class GeminiClient:

    def __init__(self) -> None:
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def to_gemini_tools(self, mcp_tools: list) -> list[types.Tool] | None:
        """MCP tool cards -> Gemini function declarations (same name, description and JSON schema)."""
        if not mcp_tools:
            return None
        declarations = [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters_json_schema=tool.inputSchema,
            )
            for tool in mcp_tools
        ]
        return [types.Tool(function_declarations=declarations)]

    def to_gemini_contents(self, history: list[dict]) -> list[types.Content]:
        """Our simple history -> Gemini messages."""
        contents = []
        for message in history:
            if message["role"] == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message["text"])]))

            elif message["role"] == "assistant":
                if message.get("raw") is not None:
                    contents.append(message["raw"])  # exact Gemini message, keeps hidden thought signatures
                else:
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(text=message["text"])]))

            elif message["role"] == "tool":
                parts = [
                    types.Part.from_function_response(name=item["name"], response=item["result"])
                    for item in message["results"]
                ]
                contents.append(types.Content(role="user", parts=parts))
        return contents

    def build_config(self, system_prompt: str, tools: list) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=self.to_gemini_tools(tools),
            temperature=0.3,
        )

    async def generate(self, system_prompt: str, history: list[dict], tools: list) -> LlmReply:
        response = await self.client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=self.to_gemini_contents(history),
            config=self.build_config(system_prompt, tools),
        )

        if not response.candidates or response.candidates[0].content is None:
            return LlmReply(text=NO_ANSWER_TEXT)

        content = response.candidates[0].content
        text = "".join(part.text for part in content.parts or [] if part.text and not part.thought)
        tool_calls = [
            ToolCall(name=call.name, arguments=dict(call.args or {}), call_id=call.id)
            for call in response.function_calls or []
        ]
        return LlmReply(text=text, tool_calls=tool_calls, raw=content)

    async def generate_stream(self, system_prompt: str, history: list[dict], tools: list) -> AsyncIterator[str | LlmReply]:
        """Yields text pieces as Gemini writes them, then one LlmReply with the full text, tool calls and raw message."""
        stream = await self.client.aio.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=self.to_gemini_contents(history),
            config=self.build_config(system_prompt, tools),
        )

        parts: list[types.Part] = []  # every part, kept to rebuild the exact message (thought signatures)
        text_pieces: list[str] = []
        tool_calls: list[ToolCall] = []
        async for chunk in stream:
            if not chunk.candidates or chunk.candidates[0].content is None:
                continue
            for part in chunk.candidates[0].content.parts or []:
                parts.append(part)
                if part.text and not part.thought:
                    text_pieces.append(part.text)
                    yield part.text
                if part.function_call:
                    call = part.function_call
                    tool_calls.append(ToolCall(name=call.name, arguments=dict(call.args or {}), call_id=call.id))

        if not parts:
            yield NO_ANSWER_TEXT
            yield LlmReply(text=NO_ANSWER_TEXT)
            return
        yield LlmReply(text="".join(text_pieces), tool_calls=tool_calls, raw=types.Content(role="model", parts=parts))


    async def embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        response = await self.client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS),
        )
        return [embedding.values for embedding in response.embeddings]


async def try_gemini() -> None:
    """Quick manual test without tools."""
    reply = await GeminiClient().generate(
        system_prompt="You are a friendly assistant. Reply in one short sentence.",
        history=[{"role": "user", "text": "Assalam o alaikum, aap kaun ho?"}],
        tools=[],
    )
    print(reply.text)


if __name__ == "__main__":
    asyncio.run(try_gemini())