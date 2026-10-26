# ClinicMate

A doctor appointment assistant for Pakistan (like oladoc / Marham) with an AI chat assistant.
Patients find doctors, see free times, book / cancel / reschedule, join waiting lists, review visits,
and ask about ClinicMate policies and general health — in **English, Urdu or Roman Urdu**.

This repository holds the server side. The Flutter app lives in its own repository (`doc_mate`).

## Architecture

```
Flutter app (doc_mate, bloc)
      │  REST + SSE (/chat/stream), Bearer token
      ▼
clinicmate_backend   (FastAPI)
      │  Gemini agent loop · tool retrieval · auth · screen APIs · background jobs · FCM
      │  starts the MCP server as a child process (stdio), sends the patient id in each call's _meta
      ▼
clinicmate_mcp_server (FastMCP, 34 tools)
      │  repositories with SQL · RAG search · password hashing · embeddings
      ▼
Supabase PostgreSQL + pgvector
```

Rules the code follows:
- The app never talks to the LLM; the API key stays on the server.
- The backend never touches the database; only the MCP server has `DATABASE_URL`.
- The MCP server never calls the chat LLM (it only makes embeddings).
- Guardrails live in code (quote before booking, patient id never chosen by the LLM, hidden internal tools).

## What is built

| Area | Highlights |
|---|---|
| Database | 14+ tables, migrations runner, seed data (60 doctors, ~3,900 slots, 300+ reviews), double-booking protection |
| MCP tools | Doctors, slots, booking (quote → confirm → book), waiting list, reviews, profile, RAG, jobs, devices, auth |
| RAG | 5 policies + 26 health guides (pgvector), doctor bios searchable by the patient's problem |
| Agent | Gemini tool loop, streaming answers (SSE), chat history per patient, strict health-safety prompt |
| Tool retrieval | Only relevant tool families are sent to the LLM per message |
| Evals | Tool selection eval and answer quality eval |
| Background agent | Hourly jobs: new slots, completed visits, waiting list offers, reminders, LLM review summaries, FCM push |
| Auth | Signup (dev OTP), login with phone + password (scrypt hash), signed tokens |
| App APIs | Doctors, slots, quote, appointments, waiting list, profile, devices |

## Run locally

Both projects have their own virtual environment.

```bash
# 1. MCP server: install, create tables, add data (first time only)
cd clinicmate_mcp_server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # fill DATABASE_URL and GEMINI_API_KEY
python -m database.run_migrations
python -m database.seed.seed_database
python -m database.seed.generate_slots
python -m scripts.ingest_knowledge_base
python -m scripts.embed_doctor_bios

# 2. Backend (it starts the MCP server by itself)
cd ../clinicmate_backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # fill the values, see clinicmate_backend/README.md
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs for all API endpoints.

More detail: [clinicmate_mcp_server/README.md](clinicmate_mcp_server/README.md) · [clinicmate_backend/README.md](clinicmate_backend/README.md)

## Still to do

- Deploy (Render) and an hourly cron job (cron-job.org → `POST /jobs/run-agents`)
- Retry on Gemini 503 and a paid API key
- Real SMS OTP instead of the development code, login rate limiting
- Firebase project key for real push notifications
- Real doctor data and a medical review of the health guides

> Seed doctors, clinics and reviews are fictional. Health guides are general information only, not medical advice.
