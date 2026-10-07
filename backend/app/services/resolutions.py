_RESOLUTIONS: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = {
    ("image", "gemini"): {
        "16:9": [("2048×1152 (2K)", "2K")],
        "9:16": [("1152×2048 (2K)", "2K")],
    },
    ("image", "fal"): {
        "16:9": [("1024×576", "1024x576")],
        "9:16": [("576×1024", "576x1024")],
    },
    ("video", "omni"): {
        "16:9": [("1280×720 (720p)", "720p")],
        "9:16": [("720×1280 (720p)", "720p")],
    },
    ("video", "fal"): {
        "16:9": [("1280×720 (720p)", "720p"), ("1920×1080 (1080p)", "1080p")],
        "9:16": [("720×1280 (720p)", "720p"), ("1080×1920 (1080p)", "1080p")],
    },
    ("video", "mock"): {
        "16:9": [("1280×720 (720p)", "720p"), ("1920×1080 (1080p)", "1080p")],
        "9:16": [("720×1280 (720p)", "720p"), ("1080×1920 (1080p)", "1080p")],
    },
}

_DEFAULT: dict[str, list[tuple[str, str]]] = {
    "16:9": [("1920×1080", "1080p"), ("1280×720", "720p")],
    "9:16": [("1080×1920", "1080p"), ("720×1280", "720p")],
}


def list_resolutions(
    kind: str, provider: str, model: str | None = None, aspect: str = "16:9"
) -> list[dict]:
    """Resoluciones disponibles para un proveedor/modelo y relación de aspecto.

    Cada opción expone ``label`` (texto legible) y ``value`` (parámetro nativo
    que se envía al proveedor).
    """
    table = _RESOLUTIONS.get((kind, provider))
    if table and aspect in table:
        return [{"label": label, "value": value} for label, value in table[aspect]]
    return [{"label": label, "value": value} for label, value in _DEFAULT.get(aspect, _DEFAULT["16:9"])]
