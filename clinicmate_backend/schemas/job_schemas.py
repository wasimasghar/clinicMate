# job_schemas.py
# Response shape of POST /jobs/run-agents.

from pydantic import BaseModel


class JobRunResponse(BaseModel):
    slots_created: int
    appointments_completed: int
    offers_expired: int
    offers_made: int
    reminders_due: int
    notifications_sent: int
    review_summaries_written: int
