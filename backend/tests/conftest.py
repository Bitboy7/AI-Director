import fakeredis.aioredis
import pytest
from arq.connections import ArqRedis
from httpx import ASGITransport, AsyncClient
from redis.asyncio import ConnectionPool


@pytest.fixture
async def fake_redis():
    pool = ConnectionPool(
        connection_class=fakeredis.aioredis.FakeAsyncRedisConnection,
        decode_responses=True,
    )
    return ArqRedis(pool)


@pytest.fixture
async def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))

    from app.config import get_settings
    from app import db

    get_settings.cache_clear()
    db.engine = None
    db._session_factory = None
    await db.init_db()
    yield db
    await db.dispose_engine()


@pytest.fixture
async def db_session(_db):
    async with _db.get_session_factory()() as session:
        yield session


@pytest.fixture
async def client(_db):
    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
