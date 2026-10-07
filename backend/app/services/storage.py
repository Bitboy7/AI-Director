import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Asset, AssetKind

ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

_KIND_DIRS = {
    AssetKind.image: "images",
    AssetKind.video: "videos",
    AssetKind.audio: "audio",
    AssetKind.episode: "episodes",
    AssetKind.upload: "uploads",
}


def project_dir(project_id: int) -> Path:
    return get_settings().storage_dir.resolve() / str(project_id)


def asset_dir(project_id: int, kind: AssetKind) -> Path:
    return project_dir(project_id) / _KIND_DIRS[kind]


async def save_upload(
    session: AsyncSession,
    project_id: int,
    kind: AssetKind,
    file: UploadFile,
) -> tuple[str, Asset]:
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("archivo no válido: solo se admiten png, jpg, jpeg y webp")

    dest_dir = asset_dir(project_id, kind)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid4().hex}{suffix}"
    max_bytes = settings.max_upload_mb * 1024 * 1024

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise ValueError(f"archivo excede el máximo de {settings.max_upload_mb} MB")
            out.write(chunk)

    rel = dest.relative_to(settings.storage_dir.resolve()).as_posix()
    asset = Asset(project_id=project_id, kind=kind, path=rel)
    session.add(asset)
    return rel, asset


def resolve_asset(relative_path: str) -> Path | None:
    settings = get_settings()
    storage = settings.storage_dir.resolve()
    candidate = (storage / relative_path).resolve()
    if (
        not candidate.is_relative_to(storage)
        or not candidate.exists()
        or not candidate.is_file()
    ):
        return None
    return candidate


async def save_generated(
    session: AsyncSession,
    project_id: int,
    kind: AssetKind,
    source: Path,
    suffix: str = ".png",
) -> str:
    settings = get_settings()
    dest_dir = asset_dir(project_id, kind)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid4().hex}{suffix}"
    shutil.copyfile(source, dest)
    rel = dest.relative_to(settings.storage_dir.resolve()).as_posix()
    asset = Asset(project_id=project_id, kind=kind, path=rel)
    session.add(asset)
    return rel
