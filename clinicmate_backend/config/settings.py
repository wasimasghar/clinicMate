# settings.py
# Reads backend configuration from the .env file in one place.

import os

from dotenv import load_dotenv

load_dotenv()


def required(name: str) -> str:
    """Value from .env, or stop with a clear error if it is missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is missing in .env")
    return value


GEMINI_API_KEY = required("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# How the backend starts the MCP server (stdio = runs it as a child process)
MCP_SERVER_PYTHON = required("MCP_SERVER_PYTHON")
MCP_SERVER_SCRIPT = required("MCP_SERVER_SCRIPT")

# Agent loop safety limit (Task 3: max rounds)
MAX_TOOL_ROUNDS = 6

# Secret header for POST /jobs/run-agents (cron-job.org). Empty = jobs endpoint disabled.
JOBS_SECRET = os.getenv("JOBS_SECRET", "")
# Login tokens are signed with this secret. Anyone who has it can make tokens, so keep it only in .env.
AUTH_SECRET = required("AUTH_SECRET")
TOKEN_VALID_DAYS = 30

# Development only: every signup OTP is this code. A real SMS service replaces it before launch.
DEV_OTP = os.getenv("DEV_OTP", "1111")

# Path to the Firebase service account JSON (Firebase Console > Project settings > Service accounts).
# Empty = notifications are only logged.
FIREBASE_CREDENTIALS_FILE = os.getenv("FIREBASE_CREDENTIALS_FILE", "")
