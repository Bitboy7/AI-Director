from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import SessionDep
from app.services import credentials as credentials_service
from app.services.verification import verify_provider

router = APIRouter(prefix="/api/v1")


class CredentialsPayload(BaseModel):
    credentials: dict[str, str] = Field(default_factory=dict)


@router.get("/settings/credentials")
async def list_credentials(session: SessionDep):
    providers = await credentials_service.list_credentials(session)
    return {"providers": providers}


@router.put("/settings/credentials/{provider}")
async def put_credentials(provider: str, payload: CredentialsPayload, session: SessionDep):
    await credentials_service.upsert_credentials(session, provider, payload.credentials)
    await session.commit()
    return {"provider": provider, "credentials": payload.credentials}


@router.delete("/settings/credentials/{provider}/{key}", status_code=204)
async def delete_credential(provider: str, key: str, session: SessionDep):
    deleted = await credentials_service.delete_credential(session, provider, key)
    if not deleted:
        raise HTTPException(status_code=404, detail="credential not found")
    await session.commit()


@router.post("/settings/credentials/{provider}/verify")
async def verify_credentials(provider: str, session: SessionDep):
    credentials = await credentials_service.get_credentials(session, provider)
    return await verify_provider(provider, credentials)
