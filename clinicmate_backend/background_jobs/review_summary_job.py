# review_summary_job.py
# The "agent" part of the background job: the LLM reads a doctor's latest reviews and writes a short, fair summary.

import logging

from llm.llm_client import LlmClient
from mcp_connection.mcp_client import McpClient

logger = logging.getLogger("review_summary_job")

SUMMARIES_PER_RUN = 5  # the job runs every hour; a few doctors per run stays inside the free LLM limits

SUMMARY_PROMPT = """You summarize patient reviews of a doctor for a doctor booking app in Pakistan.
Write 2 or 3 short sentences in simple English:
- what patients most often praise, and the most common complaint if there is one,
- mention things like waiting time, explaining clearly, behaviour with patients, clinic and fee only if reviews mention them.
Rules: use only what the reviews say, never invent; no reviewer names; no medical advice; neutral and fair tone.
Reviews can be in English, Urdu or Roman Urdu."""


def reviews_as_text(doctor: dict) -> str:
    lines = [f"Doctor: {doctor['doctor_name']} ({doctor['specialty']}), average {doctor['rating']} from {doctor['review_count']} reviews.", ""]
    lines += [f"- {review['rating']}/5: {review['comment']}" for review in doctor["reviews"]]
    return "\n".join(lines)


async def write_review_summaries(mcp: McpClient, llm: LlmClient) -> int:
    """Summarize up to SUMMARIES_PER_RUN doctors. Returns how many summaries were saved."""
    doctors = (await mcp.call_tool("get_doctors_needing_review_summary", {"limit": SUMMARIES_PER_RUN}))["doctors"]
    saved = 0
    for doctor in doctors:
        if not doctor["reviews"]:
            continue
        try:
            reply = await llm.generate(SUMMARY_PROMPT, [{"role": "user", "text": reviews_as_text(doctor)}], tools=[])
        except Exception as error:
            # LLM busy or out of quota: stop for this run, keep what is already saved, the rest waits for the next run
            logger.warning("LLM failed at doctor %s, stopping summaries for this run: %s", doctor["doctor_id"], error)
            break
        summary = reply.text.strip()
        if len(summary) < 20:
            logger.warning("empty summary for doctor %s, will retry next run", doctor["doctor_id"])
            continue
        result = await mcp.call_tool("save_review_summary", {"doctor_id": doctor["doctor_id"], "summary": summary})
        if "error" in result:
            logger.warning("could not save summary for doctor %s: %s", doctor["doctor_id"], result["error"])
            continue
        saved += 1
    return saved
