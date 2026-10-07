import sqlite3


async def test_init_db_adds_new_columns_to_existing_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE fragments (id INTEGER PRIMARY KEY, episode_id INTEGER, video_path TEXT)"
    )
    conn.execute(
        "CREATE TABLE fragment_videos (id INTEGER PRIMARY KEY, fragment_id INTEGER, path TEXT)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    from app import db
    from app.config import get_settings

    get_settings.cache_clear()
    db.engine = None
    db._session_factory = None
    await db.init_db()

    conn = sqlite3.connect(db_path)
    fragment_columns = {row[1] for row in conn.execute("PRAGMA table_info(fragments)")}
    video_columns = {row[1] for row in conn.execute("PRAGMA table_info(fragment_videos)")}
    conn.close()
    await db.dispose_engine()

    assert {"video_provider", "video_model", "resolution"} <= fragment_columns
    assert {"provider", "model", "resolution", "cost_usd"} <= video_columns
