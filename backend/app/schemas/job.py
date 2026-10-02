from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus, JobType


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: JobType
    status: JobStatus
    progress: int
    payload: dict
    result: dict
    error: str | None
    parent_id: int | None
    project_id: int | None
    created_at: datetime
    updated_at: datetime
