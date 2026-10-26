# job_runner.py
# The background agent run: housekeeping and offers on the MCP server, then notifications from the backend.

import logging

from background_jobs.reminder_job import build_reminder_notifications
from background_jobs.review_summary_job import write_review_summaries
from background_jobs.waiting_list_job import build_offer_notifications
from llm.llm_client import LlmClient
from mcp_connection.mcp_client import McpClient
from notifications.fcm_sender import send_notifications

logger = logging.getLogger("job_runner")


async def run_background_jobs(mcp: McpClient, llm: LlmClient) -> dict:
    """One run of all jobs. Safe to call often (every hour): each job only does what is still pending."""
    result = await mcp.call_tool("run_scheduled_jobs", {})
    if "error" in result:
        raise RuntimeError(result["error"])

    offer_notifications = build_offer_notifications(result["offers"])
    reminder_notifications = build_reminder_notifications(result["reminders"])
    delivered = await send_notifications(mcp, offer_notifications + reminder_notifications)

    # Mark only delivered reminders, so failed ones are tried again in the next run
    delivered_reminder_ids = [
        int(notification.data["appointment_id"])
        for notification in delivered
        if notification.data.get("type") == "reminder"
    ]
    if delivered_reminder_ids:
        await mcp.call_tool("mark_reminders_sent", {"appointment_ids": delivered_reminder_ids})

    # The LLM part: a few review summaries per run (a failure here must not undo the jobs above)
    try:
        summaries = await write_review_summaries(mcp, llm)
    except Exception as error:
        logger.warning("review summaries skipped this run: %s", error)
        summaries = 0

    summary = {**result["summary"], "notifications_sent": len(delivered), "review_summaries_written": summaries}
    logger.info("background jobs done: %s", summary)
    return summary
