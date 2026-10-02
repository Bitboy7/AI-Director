async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_module_level_app_for_uvicorn():
    from fastapi import FastAPI

    from app import main

    assert isinstance(main.app, FastAPI)
