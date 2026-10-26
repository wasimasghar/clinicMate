# run_tool_selection_eval.py
# Measures tool retrieval: for each test message, are the tools it needs among the tools we send to the LLM?
# No chat LLM calls (only embeddings), so it is cheap to run after every change. Run: python -m evals.run_tool_selection_eval

import asyncio
import json
from pathlib import Path

from agent.chat_agent import HIDDEN_TOOLS
from llm.gemini_client import GeminiClient
from mcp_connection.mcp_client import McpClient
from tool_retrieval.tool_index import ToolIndex
from tool_retrieval.tool_selector import MIN_SIMILARITY, select_tool_names

CASES_FILE = Path(__file__).parent / "datasets" / "tool_selection_cases.json"


async def run_eval() -> None:
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    mcp = McpClient()
    await mcp.connect()
    try:
        tools = [tool for tool in mcp.tools if tool.name not in HIDDEN_TOOLS]
        index = ToolIndex(GeminiClient(), tools)
        await index.build()

        passed, sent_counts = 0, []
        for case in cases:
            ranked = await index.rank(case["message"])
            selected, reason = select_tool_names(ranked, set(case.get("previous", [])))
            missing = [name for name in case["expected"] if name not in selected]
            ok = not missing
            passed += ok
            sent_counts.append(len(selected))
            top = ", ".join(f"{name} {score:.2f}" for name, score in ranked[:3])
            print(f"{'PASS' if ok else 'FAIL'}  sent {len(selected):>2}  best {ranked[0][1]:.2f}  {case['message'][:45]:<45}  top: {top}"
                  + (f"  MISSING {missing}" if missing else ""))

        print(f"\nrecall: {passed}/{len(cases)} cases have every needed tool  |  "
              f"average tools sent: {sum(sent_counts) / len(sent_counts):.1f} of {len(tools)}  |  MIN_SIMILARITY {MIN_SIMILARITY}")
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(run_eval())
