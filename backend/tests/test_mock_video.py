import asyncio

from app.providers.base import VideoSubmitPayload
from app.providers.video.mock import MockVideoProvider


async def test_mock_provider_lifecycle(tmp_path):
    provider = MockVideoProvider()
    tid = await provider.submit(
        VideoSubmitPayload(
            prompt="prueba",
            duration_seconds=3,
            aspect_ratio="16:9",
            style="cyberpunk",
            reference_images=[],
        )
    )
    status = None
    for _ in range(40):
        status = await provider.poll(tid)
        if status.state in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.25)
    assert status is not None and status.state == "succeeded", status
    dest = await provider.download(status.video_url, tmp_path / "out.mp4")
    assert dest.exists()
    assert dest.stat().st_size > 1000
