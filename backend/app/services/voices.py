import edge_tts

_FALLBACK: list[dict] = [
    {
        "short_name": "es-ES-AlvaroNeural",
        "locale": "es-ES",
        "gender": "Male",
        "friendly_name": "Microsoft Alvaro - Spanish (Spain)",
    },
    {
        "short_name": "es-MX-JorgeNeural",
        "locale": "es-MX",
        "gender": "Male",
        "friendly_name": "Microsoft Jorge - Spanish (Mexico)",
    },
    {
        "short_name": "es-AR-TomasNeural",
        "locale": "es-AR",
        "gender": "Male",
        "friendly_name": "Microsoft Tomas - Spanish (Argentina)",
    },
    {
        "short_name": "en-US-GuyNeural",
        "locale": "en-US",
        "gender": "Male",
        "friendly_name": "Microsoft Guy - English (United States)",
    },
]


async def list_voices(locale: str | None = None) -> list[dict]:
    """Lista las voces de Edge-TTS; cae a una lista estática si no hay red."""
    try:
        raw = await edge_tts.list_voices()
    except Exception:  # noqa: BLE001 - sin red, usamos la lista estática
        raw = []

    voices: list[dict] = []
    for item in raw:
        voice_locale = item.get("Locale") or ""
        if locale and not voice_locale.lower().startswith(locale.lower()):
            continue
        voices.append(
            {
                "short_name": item.get("ShortName") or item.get("Name") or "",
                "locale": voice_locale,
                "gender": item.get("Gender") or "",
                "friendly_name": item.get("FriendlyName") or item.get("ShortName") or "",
            }
        )
    if not voices:
        for item in _FALLBACK:
            if locale and not item["locale"].lower().startswith(locale.lower()):
                continue
            voices.append(item)
    return voices
