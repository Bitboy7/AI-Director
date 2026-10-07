from app.services.resolutions import list_resolutions


def test_gemini_image_resolutions_by_aspect():
    assert list_resolutions("image", "gemini", aspect="9:16")[0]["label"] == "1152×2048 (2K)"
    assert list_resolutions("image", "gemini", aspect="16:9")[0]["label"] == "2048×1152 (2K)"


def test_omni_video_resolutions():
    assert list_resolutions("video", "omni", aspect="16:9")[0]["label"] == "1280×720 (720p)"


def test_unknown_provider_uses_default():
    labels = [item["label"] for item in list_resolutions("video", "desconocido", aspect="9:16")]
    assert "1080×1920" in labels


async def test_resolutions_endpoint(client):
    r = await client.get("/api/v1/providers/video/omni/resolutions?aspect=9:16")
    assert r.status_code == 200
    assert r.json()["resolutions"][0]["label"] == "720×1280 (720p)"
