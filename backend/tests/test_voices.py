import edge_tts


async def test_voices_endpoint_filters_by_locale(client, monkeypatch):
    async def fake_list_voices(*args, **kwargs):
        return [
            {
                "ShortName": "es-MX-JorgeNeural",
                "Locale": "es-MX",
                "Gender": "Male",
                "FriendlyName": "Jorge",
            },
            {
                "ShortName": "en-US-GuyNeural",
                "Locale": "en-US",
                "Gender": "Male",
                "FriendlyName": "Guy",
            },
        ]

    monkeypatch.setattr(edge_tts, "list_voices", fake_list_voices)

    r = await client.get("/api/v1/voices?locale=es")
    assert r.status_code == 200
    assert [voice["short_name"] for voice in r.json()["voices"]] == ["es-MX-JorgeNeural"]


async def test_voices_endpoint_falls_back_without_network(client, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("sin red")

    monkeypatch.setattr(edge_tts, "list_voices", boom)

    r = await client.get("/api/v1/voices?locale=es")
    assert r.status_code == 200
    assert any(voice["short_name"].startswith("es-") for voice in r.json()["voices"])
