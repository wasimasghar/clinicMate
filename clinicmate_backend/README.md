# ClinicMate Backend

FastAPI server between the Flutter app and the MCP server. It runs the **Gemini agent** (chat), the
**screen APIs** of the app, **auth**, and the **background agent**. It starts the MCP server itself
as a child process (stdio) and never touches the database directly.

## Folders

| Folder | What is inside |
|---|---|
| `main.py` | App startup: connects to the MCP server, builds the tool index, registers routes |
| `api/` | Routes: auth, chat, doctors, appointments, waiting list, profile, devices, jobs, health; token check (`auth.py`); tool call helper (`tool_calls.py`) |
| `agent/` | `chat_agent.py` (agent loop + history), `system_prompt.py`, `response_builder.py` (cards from tool data) |
| `llm/` | `llm_client.py` (interface), `gemini_client.py` (generate, stream, embed) – Claude can be added later |
| `mcp_connection/` | `mcp_client.py`: starts the MCP server, lists tools, calls tools with the patient id in `_meta` |
| `tool_retrieval/` | Embeds tool cards; picks the tool families that fit each message |
| `streaming/` | Server-Sent Events format for `/chat/stream` |
| `background_jobs/` | Hourly run: housekeeping, waiting list offers, reminders, LLM review summaries |
| `notifications/` | FCM sender (logs only until a Firebase key is set) |
| `schemas/` | Pydantic request / response shapes = the contract with the app |
| `evals/` | Tool selection and answer quality evaluations with their datasets |

## How one chat message works

```
POST /chat/stream {conversation_id, message} + Bearer token
  → token → patient id → load history (memory, or DB through MCP after a restart)
  → pick relevant tools (tool retrieval)
  → Gemini → tool call? → MCP tool (patient id in _meta) → result back to Gemini → … (max 6 rounds)
  → SSE events: status ("Searching doctors…"), token (text pieces), done (reply + doctor cards +
    booking card + sources + disclaimer)
  → save question + answer for logged-in patients
```

## API

| Group | Endpoints | Login |
|---|---|---|
| Auth | `POST /auth/send-otp`, `POST /auth/signup`, `POST /auth/login` | – |
| Chat | `POST /chat`, `POST /chat/stream` (SSE) | optional |
| Doctors | `GET /specialties`, `GET /cities`, `GET /doctors`, `GET /doctors/{id}`, `GET /doctors/{id}/reviews`, `GET /doctors/{id}/slots`, `GET /slots/{slot_id}/quote` | – |
| Appointments | `GET/POST /appointments`, `POST /appointments/{id}/cancel`, `/reschedule`, `/review` | yes |
| Waiting list | `GET/POST /waiting-list`, `DELETE /waiting-list/{id}` | yes |
| Profile | `GET /me`, `PATCH /me` | yes |
| Devices | `POST /devices`, `DELETE /devices` (FCM token) | yes |
| Jobs | `POST /jobs/run-agents` (header `X-Jobs-Secret`) | secret |
| Health | `GET /health` | – |

Full request / response shapes: http://localhost:8000/docs

Errors come as `{"detail": "message"}`: 401 = sign in again, 404 = not found, 409 = slot already taken,
400 = rule broken (readable message), 503 = assistant busy.

## Setup and run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

| Key | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini chat + embeddings |
| `GEMINI_MODEL` | Chat model, e.g. `gemini-3.5-flash-lite` |
| `MCP_SERVER_PYTHON` | Absolute path to `clinicmate_mcp_server/.venv/bin/python` |
| `MCP_SERVER_SCRIPT` | Absolute path to `clinicmate_mcp_server/server.py` |
| `AUTH_SECRET` | Signs login tokens. Make one: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DEV_OTP` | Development signup code (default `1111`) until a real SMS service is added |
| `JOBS_SECRET` | Secret header for `/jobs/run-agents`; empty = jobs endpoint disabled |
| `FIREBASE_CREDENTIALS_FILE` | Path to the Firebase service account JSON; empty = notifications are only logged |

## Evals

```bash
python -m evals.run_tool_selection_eval    # embeddings only, cheap
python -m evals.run_answer_quality_eval    # real chats with Gemini (uses quota)
```

The answer quality eval checks: the right tool was used, reply language and script match the user,
health answers show the disclaimer, no medicine names, emergency advice (1122), and out-of-scope questions
use no booking tools.
