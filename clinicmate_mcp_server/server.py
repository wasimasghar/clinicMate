# server.py
# ClinicMate MCP server: creates the server, registers all tools and runs over stdio.

import logging
import sys

from mcp.server.fastmcp import FastMCP

from tools.account_tools import register_account_tools
from tools.appointment_tools import register_appointment_tools
from tools.chat_history_tools import register_chat_history_tools
from tools.device_tools import register_device_tools
from tools.doctor_tools import register_doctor_tools
from tools.slot_tools import register_slot_tools
from tools.review_tools import register_review_tools
from tools.knowledge_tools import register_knowledge_tools
from tools.job_tools import register_job_tools
from tools.waiting_list_tools import register_waiting_list_tools
from tools.auth_tools import register_auth_tools
# Logs go to stderr. stdout is reserved for MCP messages, so never use print() here.
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")

mcp = FastMCP(
    "clinicmate",
    instructions=(
        "ClinicMate helps patients in Pakistan find doctors and book appointments. "
        "Fees are in PKR and all times are Pakistan time. "
        "Use list_specialties to pick an exact specialty before search_doctors. "
        "Doctor, slot and appointment ids must come from earlier tool results; never invent them."
    ),
)

register_doctor_tools(mcp)
register_slot_tools(mcp)
register_appointment_tools(mcp)
register_account_tools(mcp)
register_review_tools(mcp)
register_knowledge_tools(mcp)
register_chat_history_tools(mcp)
register_waiting_list_tools(mcp)
register_job_tools(mcp)
register_device_tools(mcp)
register_auth_tools(mcp)
if __name__ == "__main__":
    mcp.run(transport="stdio")