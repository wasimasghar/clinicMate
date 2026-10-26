# job_routes.py
# POST /jobs/run-agents: called every hour by cron-job.org with a secret header to run the background agent.

import secrets

from fastapi import APIRouter, Header, HTTPException, Request

from background_jobs.job_runner import run_background_jobs
from config.settings import JOBS_SECRET
from schemas.job_schemas import JobRunResponse

router = APIRouter()


@router.post("/jobs/run-agents", response_model=JobRunResponse)
async def run_agents(request: Request, x_jobs_secret: str | None = Header(default=None)) -> JobRunResponse:
    if not JOBS_SECRET:
        raise HTTPException(status_code=503, detail="Background jobs are not configured (JOBS_SECRET missing).")
    # compare_digest takes the same time for any wrong secret, so the secret cannot be guessed by timing
    if not x_jobs_secret or not secrets.compare_digest(x_jobs_secret, JOBS_SECRET):
        raise HTTPException(status_code=401, detail="Wrong or missing X-Jobs-Secret header.")
    summary = await run_background_jobs(request.app.state.mcp, request.app.state.agent.llm)
    return JobRunResponse(**summary)
