from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.models import ApiCall
from app.schemas.stats import ApiCallRead, StatsResponse, StatsTotals

router = APIRouter(prefix="/api/v1")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    session: SessionDep,
    project_id: int | None = None,
    kind: str | None = None,
    limit: int = 100,
):
    query = select(ApiCall)
    totals_query = select(
        func.count(ApiCall.id),
        func.coalesce(func.sum(ApiCall.cost_usd), 0.0),
        func.coalesce(func.sum(ApiCall.input_tokens), 0),
        func.coalesce(func.sum(ApiCall.output_tokens), 0),
        func.coalesce(func.sum(ApiCall.duration_ms), 0),
    )
    if project_id is not None:
        query = query.where(ApiCall.project_id == project_id)
        totals_query = totals_query.where(ApiCall.project_id == project_id)
    if kind:
        query = query.where(ApiCall.kind == kind)
        totals_query = totals_query.where(ApiCall.kind == kind)

    query = query.order_by(ApiCall.id.desc()).limit(max(1, min(limit, 500)))
    calls = list((await session.execute(query)).scalars().all())
    count, cost, input_tokens, output_tokens, duration_ms = (
        await session.execute(totals_query)
    ).one()

    return StatsResponse(
        calls=[ApiCallRead.model_validate(call) for call in calls],
        totals=StatsTotals(
            count=int(count),
            cost_usd=float(cost),
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            duration_ms=int(duration_ms),
        ),
    )
