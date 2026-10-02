from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import SessionDep
from app.api.projects import get_project_or_404
from app.models import AssetKind, ImageOrigin, ReferenceImage, Resource, ResourceVariant
from app.schemas import (
    ReferenceImageRead,
    ResourceCreate,
    ResourceRead,
    ResourceVariantCreate,
    ResourceVariantRead,
    ResourceVariantUpdate,
)
from app.services.storage import save_upload

router = APIRouter(prefix="/api/v1")


async def get_resource_or_404(session: SessionDep, resource_id: int) -> Resource:
    resource = await session.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return resource


async def get_variant_or_404(session: SessionDep, variant_id: int) -> ResourceVariant:
    variant = await session.get(ResourceVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="variant not found")
    return variant


async def load_resource(session: SessionDep, resource_id: int) -> Resource:
    result = await session.execute(select(Resource).where(Resource.id == resource_id))
    return result.scalar_one()


async def load_variant(session: SessionDep, variant_id: int) -> ResourceVariant:
    result = await session.execute(
        select(ResourceVariant).where(ResourceVariant.id == variant_id)
    )
    return result.scalar_one()


@router.get("/projects/{project_id}/resources", response_model=list[ResourceRead])
async def list_resources(project_id: int, session: SessionDep):
    await get_project_or_404(session, project_id)
    result = await session.execute(
        select(Resource).where(Resource.project_id == project_id).order_by(Resource.id)
    )
    return list(result.scalars())


@router.post("/projects/{project_id}/resources", response_model=ResourceRead)
async def create_resource(project_id: int, payload: ResourceCreate, session: SessionDep):
    await get_project_or_404(session, project_id)
    resource = Resource(
        project_id=project_id,
        type=payload.type.value,
        name=payload.name,
        profile=payload.profile,
    )
    session.add(resource)
    await session.commit()
    return await load_resource(session, resource.id)


@router.patch("/resources/{resource_id}", response_model=ResourceRead)
async def update_resource(resource_id: int, payload: ResourceCreate, session: SessionDep):
    resource = await get_resource_or_404(session, resource_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "type":
            value = value.value
        setattr(resource, field, value)
    await session.commit()
    return await load_resource(session, resource_id)


@router.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(resource_id: int, session: SessionDep):
    resource = await get_resource_or_404(session, resource_id)
    await session.delete(resource)
    await session.commit()


@router.post(
    "/resources/{resource_id}/variants", response_model=ResourceVariantRead
)
async def create_variant(
    resource_id: int, payload: ResourceVariantCreate, session: SessionDep
):
    await get_resource_or_404(session, resource_id)
    variant = ResourceVariant(
        resource_id=resource_id,
        name=payload.name,
        description=payload.description,
        episodes=payload.episodes,
        image_model=payload.image_model,
        image_style=payload.image_style,
        voice=payload.voice,
    )
    session.add(variant)
    await session.commit()
    return await load_variant(session, variant.id)


@router.patch("/variants/{variant_id}", response_model=ResourceVariantRead)
async def update_variant(
    variant_id: int, payload: ResourceVariantUpdate, session: SessionDep
):
    variant = await get_variant_or_404(session, variant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    await session.commit()
    return await load_variant(session, variant_id)


@router.delete("/variants/{variant_id}", status_code=204)
async def delete_variant(variant_id: int, session: SessionDep):
    variant = await get_variant_or_404(session, variant_id)
    await session.delete(variant)
    await session.commit()


@router.post("/variants/{variant_id}/images", response_model=ReferenceImageRead)
async def upload_reference_image(
    variant_id: int, session: SessionDep, file: UploadFile = File(...)
):
    variant = await get_variant_or_404(session, variant_id)
    resource = await session.get(Resource, variant.resource_id)
    project_id = resource.project_id
    try:
        rel, _asset = await save_upload(session, project_id, AssetKind.image, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    image = ReferenceImage(
        variant_id=variant_id, path=rel, origin=ImageOrigin.uploaded, kind="reference"
    )
    session.add(image)
    await session.commit()
    return image


@router.post("/variants/{variant_id}/images/generate", status_code=501)
async def generate_reference_image(variant_id: int):
    raise HTTPException(status_code=501, detail="image_provider_not_configured")
