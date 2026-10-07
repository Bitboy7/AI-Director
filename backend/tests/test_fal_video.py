import httpx
import pytest

from app.providers.base import ProviderAuthError, ProviderRateLimitError, VideoSubmitPayload
from app.providers.video.fal import FalVideoProvider

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"fake-video"
VIDEO_URL = "https://v3.fal.media/files/abc/video.mp4"
QUEUE_URL = "https://queue.fal.run/fal-ai/kling-video/v2.1/pro/text-to-video"
STATUS_URL = "https://queue.fal.run/req_abc/status"
RESULT_URL = "https://queue.fal.run/req_abc"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-ref-image"


def queue_submit_response() -> dict:
    return {
        "request_id": "req_abc",
        "status_url": STATUS_URL,
        "response_url": RESULT_URL,
        "cancel_url": "https://queue.fal.run/req_abc/cancel",
    }


def make_payload(**overrides) -> VideoSubmitPayload:
    defaults = {
        "prompt": "una nave despegando",
        "duration_seconds": 6,
        "aspect_ratio": "16:9",
        "style": "",
        "reference_images": [],
    }
    defaults.update(overrides)
    return VideoSubmitPayload(**defaults)


def capture_handler(captured):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            if "/status" in str(request.url):
                return httpx.Response(
                    200, json={"status": "COMPLETED", "request_id": "req_abc"}
                )
            return httpx.Response(
                200,
                json={"video": {"url": VIDEO_URL, "content_type": "video/mp4"}},
            )
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=queue_submit_response())

    return handler


async def test_submit_uses_queue_with_prompt_and_aspect():
    captured = {}
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(capture_handler(captured))
    )

    task_id = await provider.submit(make_payload())

    assert task_id == "req_abc"
    assert captured["url"] == QUEUE_URL
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["prompt"] == "una nave despegando"
    assert body["aspect_ratio"] == "16:9"
    assert body["duration"] == "6"


async def test_submit_with_reference_image_switches_to_image_to_video(tmp_path):
    image = tmp_path / "ref.png"
    image.write_bytes(PNG_BYTES)
    captured = {}
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(capture_handler(captured)),
    )

    await provider.submit(make_payload(reference_images=[image]))

    assert captured["url"].endswith("/image-to-video")
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["image_url"].startswith("data:image/png;base64,")


async def test_submit_without_reference_image_keeps_text_to_video():
    captured = {}
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(capture_handler(captured)),
    )

    await provider.submit(make_payload())

    assert captured["url"].endswith("/text-to-video")
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert "image_url" not in body


async def test_submit_keeps_image_model_and_encodes_jpeg(tmp_path):
    image = tmp_path / "ref.jpg"
    image.write_bytes(b"fake-jpeg")
    captured = {}
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"},
        model="fal-ai/kling-video/v2.1/pro/image-to-video",
        transport=httpx.MockTransport(capture_handler(captured)),
    )

    await provider.submit(make_payload(reference_images=[image]))

    assert captured["url"].endswith("/image-to-video")
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["image_url"].startswith("data:image/jpeg;base64,")


async def test_submit_retries_with_prompt_only_when_args_rejected():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"status": "IN_QUEUE"})
        calls.append(httpx.Response(200, content=request.content.decode()).json())
        if len(calls) == 1:
            return httpx.Response(422, json={"detail": "unknown argument 'aspect_ratio'"})
        return httpx.Response(200, json=queue_submit_response())

    provider = FalVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    task_id = await provider.submit(make_payload())

    assert task_id == "req_abc"
    assert len(calls) == 2
    assert calls[1] == {"prompt": "una nave despegando"}


async def test_poll_returns_processing_while_in_progress():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"status": "IN_PROGRESS", "request_id": "req_abc"})
        return httpx.Response(200, json=queue_submit_response())

    provider = FalVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    await provider.submit(make_payload())
    status = await provider.poll("req_abc")

    assert status.state == "processing"
    assert status.video_url is None


async def test_poll_completed_fetches_video_url():
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(capture_handler({})),
    )
    await provider.submit(make_payload())
    status = await provider.poll("req_abc")

    assert status.state == "succeeded"
    assert status.video_url == VIDEO_URL


async def test_poll_failed_reports_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/status" in str(request.url):
            return httpx.Response(200, json={"status": "FAILED", "request_id": "req_abc"})
        return httpx.Response(200, json=queue_submit_response())

    provider = FalVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    await provider.submit(make_payload())
    status = await provider.poll("req_abc")

    assert status.state == "failed"
    assert status.error


async def test_download_from_http_url(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=VIDEO_BYTES)

    provider = FalVideoProvider(
        credentials={"api_key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    dest = tmp_path / "out.mp4"
    await provider.download(VIDEO_URL, dest)
    assert dest.read_bytes() == VIDEO_BYTES


async def test_submit_auth_error_maps_to_provider_auth_error():
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(lambda request: httpx.Response(401, json={})),
    )
    with pytest.raises(ProviderAuthError):
        await provider.submit(make_payload())


async def test_submit_auth_error_includes_fal_detail():
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(
            lambda request: httpx.Response(403, json={"detail": "Exhausted balance. Top up."})
        ),
    )
    with pytest.raises(ProviderAuthError) as excinfo:
        await provider.submit(make_payload())
    assert "Exhausted balance" in str(excinfo.value)


async def test_submit_rate_limit_maps_to_provider_rate_limit_error():
    provider = FalVideoProvider(
        credentials={"api_key": "test-key"},
        transport=httpx.MockTransport(lambda request: httpx.Response(429, json={})),
    )
    with pytest.raises(ProviderRateLimitError):
        await provider.submit(make_payload())


async def test_missing_api_key_raises_auth_error(monkeypatch):
    monkeypatch.delenv("FAL_API_KEY", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(ProviderAuthError):
        FalVideoProvider(credentials={})


async def test_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "env-key")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"status": "IN_QUEUE"})
        captured["key"] = request.headers.get("authorization")
        return httpx.Response(200, json=queue_submit_response())

    provider = FalVideoProvider(credentials={}, transport=httpx.MockTransport(handler))
    await provider.submit(make_payload())
    assert captured["key"] == "Key env-key"