from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global engine, _session_factory
    if engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        engine = create_async_engine(settings.database_url, connect_args=connect_args)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "fragments": {
        "video_provider": "VARCHAR(50)",
        "video_model": "VARCHAR(200)",
        "resolution": "VARCHAR(50)",
    },
    "fragment_videos": {
        "provider": "VARCHAR(50) DEFAULT ''",
        "model": "VARCHAR(200) DEFAULT ''",
        "resolution": "VARCHAR(50)",
        "cost_usd": "FLOAT DEFAULT 0",
    },
}


async def _ensure_columns(conn) -> None:
    """Add columns introduced after a database already existed (SQLite only)."""
    if not str(get_engine().url).startswith("sqlite"):
        return
    for table, columns in _ADDED_COLUMNS.items():
        existing = {
            row[1]
            for row in (await conn.exec_driver_sql(f"PRAGMA table_info({table})")).fetchall()
        }
        if not existing:
            continue
        for name, ddl in columns.items():
            if name not in existing:
                await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


async def init_db() -> None:
    from app import models  # noqa: F401

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_columns(conn)


async def dispose_engine() -> None:
    global engine, _session_factory
    if engine is not None:
        await engine.dispose()
    engine = None
    _session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session
