from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.storage import resolve_asset

router = APIRouter(prefix="/api/v1")


@router.get("/assets/{path:path}")
async def serve_asset(path: str):
    resolved = resolve_asset(path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(resolved)
