import redis.exceptions

from app.jobs import run as run_module


async def test_worker_retries_redis_connection(monkeypatch):
    calls = {"n": 0}

    class FakeWorker:
        def __init__(self, **kwargs):
            pass

        async def async_run(self):
            calls["n"] += 1
            if calls["n"] == 1:
                raise redis.exceptions.ConnectionError("redis caído")
            return None

    monkeypatch.setattr(run_module, "Worker", FakeWorker)

    await run_module.run_worker_with_retries("default", retry_delay=0)

    assert calls["n"] == 2
