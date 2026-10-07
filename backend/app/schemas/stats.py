from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    job_id: int | None
    kind: str
    provider: str
    model: str
    status: str
    duration_ms: int
    input_tokens: int
    output_tokens: int
    units: float
    cost_usd: float
    error: str | None
    created_at: datetime


class StatsTotals(BaseModel):
    count: int
    cost_usd: float
    input_tokens: int
    output_tokens: int
    duration_ms: int


class StatsResponse(BaseModel):
    calls: list[ApiCallRead]
    totals: StatsTotals
