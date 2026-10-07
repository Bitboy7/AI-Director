from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import SessionDep
from app.providers import list_all_providers
from app.providers.base import ProviderAuthError
from app.services import credentials as credentials_service
from app.services.models import list_provider_models
from app.services.resolutions import list_resolutions
from app.services.usage import model_pricing
from app.services.verification import verify_provider

router = APIRouter(prefix="/api/v1")

_NO_KEY_PROVIDERS = {"ollama", "edge", "mock"}


class CredentialsPayload(BaseModel):
    credentials: dict[str, str] = Field(default_factory=dict)


async def providers_with_configuration(
    session: SessionDep, credentials_service
) -> dict[str, list[dict]]:
    catalog = list_all_providers()
    result: dict[str, list[dict]] = {}
    for kind, names in catalog.items():
        result[kind] = []
        for name in names:
            configured = name in _NO_KEY_PROVIDERS
            if not configured:
                creds = await credentials_service.get_credentials(session, name)
                configured = bool(creds.get("api_key") or creds.get("endpoint"))
            result[kind].append({"name": name, "configured": configured})
    return result


@router.get("/providers")
async def list_providers(session: SessionDep):
    return {"providers": await providers_with_configuration(session, credentials_service)}


@router.get("/providers/{kind}/{name}/models")
async def provider_models(kind: str, name: str, session: SessionDep):
    credentials = await credentials_service.get_credentials(session, name)
    try:
        models = await list_provider_models(kind, name, credentials)
    except ProviderAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    for model in models:
        model["pricing"] = model_pricing(kind, model.get("id", ""))
    return {"models": models}


@router.get("/providers/{kind}/{name}/resolutions")
async def provider_resolutions(
    kind: str, name: str, aspect: str = "16:9", model: str | None = None
):
    return {"resolutions": list_resolutions(kind, name, model, aspect)}


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
