import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProviderCredential

_FALLBACK_KEYS = ("api_key", "endpoint")


async def get_credentials(session: AsyncSession, provider: str) -> dict[str, str]:
    result = await session.execute(
        select(ProviderCredential).where(ProviderCredential.provider == provider)
    )
    credentials = {row.key: row.value for row in result.scalars()}
    for key in _FALLBACK_KEYS:
        if key not in credentials:
            env_value = os.environ.get(f"{provider.upper()}_{key.upper()}")
            if env_value:
                credentials[key] = env_value
    return credentials


async def upsert_credentials(
    session: AsyncSession, provider: str, values: dict[str, str]
) -> list[ProviderCredential]:
    result = await session.execute(
        select(ProviderCredential).where(ProviderCredential.provider == provider)
    )
    existing = {row.key: row for row in result.scalars()}
    for key in list(existing.keys()):
        if key not in values:
            await session.delete(existing.pop(key))
    for key, value in values.items():
        if key in existing:
            existing[key].value = value
        else:
            row = ProviderCredential(provider=provider, key=key, value=value)
            session.add(row)
            existing[key] = row
    return list(existing.values())


async def list_credentials(session: AsyncSession) -> dict[str, dict[str, str]]:
    result = await session.execute(select(ProviderCredential).order_by(ProviderCredential.provider))
    grouped: dict[str, dict[str, str]] = {}
    for row in result.scalars():
        grouped.setdefault(row.provider, {})[row.key] = row.value
    return grouped


async def delete_credential(session: AsyncSession, provider: str, key: str) -> bool:
    result = await session.execute(
        select(ProviderCredential).where(
            ProviderCredential.provider == provider, ProviderCredential.key == key
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    return True
