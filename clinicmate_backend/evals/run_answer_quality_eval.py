# run_answer_quality_eval.py
# Runs real chats through the agent (Gemini + MCP) and checks the answers with simple rules:
# right tool used, reply language, health disclaimer, no medicine names, emergency advice, out-of-scope behaviour.
# Uses the LLM, so it costs requests; run it after prompt or tool changes. Run: python -m evals.run_answer_quality_eval

import asyncio
import json
import re
from pathlib import Path

from agent.chat_agent import ChatAgent
from agent.response_builder import build_chat_response
from llm.gemini_client import GeminiClient
from mcp_connection.mcp_client import McpClient
from tool_retrieval.tool_index import ToolIndex

CASES_FILE = Path(__file__).parent / "datasets" / "answer_quality_cases.json"
EVAL_PATIENT_ID = 1           # read-only questions, run as seed patient 1
URDU_SCRIPT = re.compile(r"[؀-ۿ]")


def check_case(case: dict, reply: str, tools_used: list[str], show_disclaimer: bool) -> list[str]:
    """Problems found in one answer (empty list = pass)."""
    problems = []
    lower = reply.lower()
    if not reply.strip():
        problems.append("empty reply")
    if case.get("expect_tools_any") and not set(case["expect_tools_any"]) & set(tools_used):
        problems.append(f"expected one of {case['expect_tools_any']}, used {tools_used}")
    for tool in case.get("forbid_tools", []):
        if tool in tools_used:
            problems.append(f"should not use {tool}")
    if case.get("language") in ("roman_urdu", "english") and URDU_SCRIPT.search(reply):
        problems.append("replied in Urdu script")
    if case.get("language") == "urdu" and not URDU_SCRIPT.search(reply):
        problems.append("did not reply in Urdu script")
    if case.get("expect_disclaimer") and not show_disclaimer:
        problems.append("health disclaimer missing")
    for word in case.get("must_not_contain", []):
        if re.search(rf"\b{re.escape(word)}\b", lower):
            problems.append(f"contains forbidden '{word}'")
    if case.get("must_contain_any") and not any(word.lower() in lower for word in case["must_contain_any"]):
        problems.append(f"should mention one of {case['must_contain_any']}")
    return problems


async def run_eval() -> None:
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    mcp = McpClient()
    await mcp.connect()
    try:
        llm = GeminiClient()
        agent = ChatAgent(llm=llm, mcp=mcp)
        agent.tool_index = ToolIndex(llm, agent.llm_tools)
        await agent.tool_index.build()

        passed = 0
        for number, case in enumerate(cases, start=1):
            try:
                result = await agent.run_turn(f"eval-{number}", case["message"], EVAL_PATIENT_ID)
            except Exception as error:
                print(f"ERROR {case['message'][:50]}: {error}")
                continue
            response = build_chat_response(f"eval-{number}", result)
            tools_used = [call["name"] for call in result.tool_calls]
            problems = check_case(case, response.reply, tools_used, response.show_disclaimer)
            passed += not problems
            print(f"{'PASS' if not problems else 'FAIL'}  {case['message'][:55]:<55} tools={tools_used}")
            for problem in problems:
                print(f"      - {problem}")
            if problems:
                print(f"      reply: {response.reply[:200]!r}")

        print(f"\nanswer quality: {passed}/{len(cases)} passed")
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(run_eval())
