import base64
from pathlib import Path

import httpx
import pytest

from app.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    VideoSubmitPayload,
)
from app.providers.video.omni import OmniVideoProvider

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"fake-video-data"
URI = "https://generativelanguage.googleapis.com/v1beta/files/abc123:download?alt=media"


def video_interaction_response(
    status: str = "completed",
    data: bytes | None = None,
    uri: str | None = None,
    video_id: str = "v1_vid_1",
) -> dict:
    content: dict = {"type": "video", "mime_type": "video/mp4"}
    if data is not None:
        content["data"] = base64.b64encode(data).decode()
    if uri is not None:
        content["uri"] = uri
    return {
        "id": video_id,
        "object": "interaction",
        "model": "gemini-omni-1.1-flash",
        "status": status,
        "steps": [{"type": "model_output", "content": [content]}],
    }


def make_payload(**overrides) -> VideoSubmitPayload:
    defaults = {
        "prompt": "una ola rompiendo en la playa",
        "duration_seconds": 5,
        "aspect_ratio": "16:9",
        "style": "",
        "reference_images": [],
    }
    defaults.update(overrides)
    return VideoSubmitPayload(**defaults)


async def test_submit_text_to_video_sends_prompt_and_task():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=video_interaction_response(status="running"))

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    task_id = await provider.submit(make_payload())

    assert task_id == "v1_vid_1"
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["model"] == "gemini-omni-1.1-flash"
    assert body["background"] is True
    assert body["input"] == "una ola rompiendo en la playa"
    assert body["generation_config"]["video_config"]["task"] == "text_to_video"
    assert body["response_format"]["aspect_ratio"] == "16:9"
    assert body["response_format"]["duration"] == "5s"


async def test_submit_with_reference_images_uses_image_to_video(tmp_path):
    images = []
    for name, content in [("a.png", b"png-bytes"), ("b.jpg", b"jpg-bytes"), ("c.png", b"extra")]:
        path = tmp_path / name
        path.write_bytes(content)
        images.append(path)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=video_interaction_response(status="running"))

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    await provider.submit(make_payload(reference_images=images))

    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["generation_config"]["video_config"]["task"] == "image_to_video"
    assert [item["type"] for item in body["input"]] == ["image", "image", "text"]
    assert body["input"][0]["mime_type"] == "image/png"
    assert body["input"][0]["data"] == base64.b64encode(b"png-bytes").decode()
    assert body["input"][1]["mime_type"] == "image/jpeg"
    assert body["input"][2]["text"].endswith("una ola rompiendo en la playa")


async def test_duration_is_clamped_to_ten_seconds():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=video_interaction_response(status="running"))

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    await provider.submit(make_payload(duration_seconds=15))

    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["response_format"]["duration"] == "10s"


async def test_poll_returns_processing_while_running():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=video_interaction_response(status="running"))

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    status = await provider.poll("v1_vid_1")
    assert status.state == "processing"
    assert status.video_url is None


async def test_poll_completed_inline_saves_video_file():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=video_interaction_response(data=VIDEO_BYTES))

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    status = await provider.poll("v1_vid_1")
    assert status.state == "succeeded"
    assert status.video_url is not None
    assert Path(status.video_url).read_bytes() == VIDEO_BYTES


async def test_poll_completed_uri_polls_file_until_active():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/files/" in str(request.url) and ":download" not in str(request.url):
            return httpx.Response(200, json={"name": "files/abc123", "state": "ACTIVE"})
        return httpx.Response(200, json=video_interaction_response(uri=URI))

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    status = await provider.poll("v1_vid_1")
    assert status.state == "succeeded"
    assert status.video_url == URI


async def test_poll_failed_returns_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=video_interaction_response(status="failed"))

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    status = await provider.poll("v1_vid_1")
    assert status.state == "failed"
    assert status.error


async def test_submit_auth_error_maps_to_provider_auth_error():
    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(lambda request: httpx.Response(401, json={})),
    )
    with pytest.raises(ProviderAuthError):
        await provider.submit(make_payload())


async def test_submit_rate_limit_maps_to_provider_rate_limit_error():
    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(lambda request: httpx.Response(429, json={})),
    )
    with pytest.raises(ProviderRateLimitError):
        await provider.submit(make_payload())


async def test_missing_api_key_raises_auth_error(monkeypatch):
    monkeypatch.delenv("OMNI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError):
        OmniVideoProvider(credentials={})


async def test_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("OMNI_API_KEY", "env-key")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json=video_interaction_response(status="running"))

    provider = OmniVideoProvider(credentials={}, transport=httpx.MockTransport(handler))
    await provider.submit(make_payload())
    assert captured["key"] == "env-key"


async def test_download_from_http_url(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=VIDEO_BYTES)

    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    dest = tmp_path / "out.mp4"
    await provider.download(URI, dest)
    assert dest.read_bytes() == VIDEO_BYTES


async def test_download_copies_local_file(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(VIDEO_BYTES)
    provider = OmniVideoProvider(credentials={"api_key": "test-key"})
    dest = tmp_path / "out.mp4"
    await provider.download(str(src), dest)
    assert dest.read_bytes() == VIDEO_BYTES


async def test_submit_server_error_maps_to_unavailable():
    provider = OmniVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(lambda request: httpx.Response(500, json={})),
    )
    with pytest.raises(ProviderUnavailableError):
        await provider.submit(make_payload())
