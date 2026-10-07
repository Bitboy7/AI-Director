from fastapi import APIRouter

from app.services.styles import list_styles

router = APIRouter(prefix="/api/v1")


@router.get("/styles")
async def get_styles() -> dict:
    return {"styles": [{"id": style.id, "label": style.label} for style in list_styles()]}
