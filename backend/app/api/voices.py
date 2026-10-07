from fastapi import APIRouter

from app.services.voices import list_voices

router = APIRouter(prefix="/api/v1")


@router.get("/voices")
async def get_voices(locale: str | None = None):
    return {"voices": await list_voices(locale)}
