# ClinicMate MCP Server

The tool server of ClinicMate (Python, FastMCP 1.x). It owns the database and exposes **34 tools**.
The backend starts it as a child process over **stdio**; for testing it also works with
MCP Inspector and Claude Desktop.

```
Tool (tools/)  →  Repository (repositories/, SQL)  →  Supabase PostgreSQL + pgvector
```

## Folders

| Folder | What is inside |
|---|---|
| `server.py` | Creates the FastMCP server and registers every tool group |
| `config/` | Reads `.env` (`settings.py`) |
| `database/` | Connection pool, SQL migrations, migration runner, seed data and seed scripts |
| `repositories/` | All SQL: doctors, slots, appointments, patients, reviews, waiting list, devices, chat, knowledge |
| `tools/` | MCP tools (thin: call a repository, shape the result for the LLM, return small JSON) |
| `services/` | Session / patient identity, Gemini embeddings, password hashing |
| `knowledge_base/` | Markdown policies and health guides used for RAG |
| `scripts/` | Ingest the knowledge base, embed doctor bios |

## Tools

| Group | Tools | Who uses them |
|---|---|---|
| Doctors | `list_specialties`, `list_cities`, `search_doctors` (filters + `need` meaning search), `get_doctor_profile` | LLM + app |
| Slots | `get_available_slots` | LLM + app |
| Appointments | `quote_appointment`, `book_appointment`, `cancel_appointment`, `reschedule_appointment`, `get_my_appointments` | LLM + app |
| Reviews | `get_doctor_reviews`, `add_review` | LLM + app |
| Waiting list | `join_waiting_list`, `get_my_waiting_list`, `leave_waiting_list` | LLM + app |
| Account | `get_my_profile`, `update_my_profile`; `login`, `register`, `logout` (Claude Desktop only) | LLM + app |
| Knowledge (RAG) | `search_policies`, `search_health_guides` | LLM |
| Auth | `create_account`, `verify_login` | backend only |
| Chat history | `save_conversation_turn`, `get_conversation_history` | backend only |
| Devices (FCM) | `save_device_token`, `remove_device_token`, `get_device_tokens`, `remove_dead_device_tokens` | backend only |
| Background jobs | `run_scheduled_jobs`, `mark_reminders_sent`, `get_doctors_needing_review_summary`, `save_review_summary` | backend only |

## Important design choices

- **Patient identity:** when the backend starts this server it sets `TRUST_CLIENT_PATIENT_ID=true` and sends
  the logged-in patient's id in every call's `_meta`. The LLM never chooses a patient id.
  Without that flag (Claude Desktop / Inspector) the chat `login` tool is used instead.
- **Backend-only tools** refuse to run for single-user clients, and the backend hides them from the LLM.
- **Booking safety:** a slot can be booked only after `quote_appointment` (valid 10 minutes); row locks and a
  partial unique index stop double booking; every write is one transaction.
- **RAG:** markdown files are split by `##` heading, embedded with `gemini-embedding-001` (768), searched with
  pgvector cosine distance and a tuned distance limit; results include sources.
- **Passwords** are hashed with scrypt (standard library); only the hash is stored.
- No `print()` inside the server: stdout is the MCP channel. Logs go to stderr.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DATABASE_URL = Supabase "Session pooler" URI, GEMINI_API_KEY for embeddings
```

| Command | What it does |
|---|---|
| `python -m database.run_migrations` | Runs new files in `database/migrations/` (skips ones already applied) |
| `python -m database.seed.generate_reviews` | Writes `database/seed/data/reviews.json` |
| `python -m database.seed.seed_database` | Loads cities, specialties, clinics, doctors, schedules, patients, reviews |
| `python -m database.seed.generate_slots` | Creates free slots for the next 14 days (safe to run again) |
| `python -m scripts.ingest_knowledge_base` | Chunks + embeds changed knowledge base files |
| `python -m scripts.embed_doctor_bios` | Embeds doctor "about" texts for problem-based search |

Test the tools without the backend:

```bash
npx @modelcontextprotocol/inspector .venv/bin/python server.py
```

## Environment variables

| Key | Purpose |
|---|---|
| `DATABASE_URL` | Supabase PostgreSQL connection (Session pooler, port 5432) |
| `GEMINI_API_KEY` | Embeddings for RAG and doctor search |
| `TRUST_CLIENT_PATIENT_ID` | Set by the backend only (`true`); do not put it in `.env` |
