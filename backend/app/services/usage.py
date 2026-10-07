from app.models import ApiCall

# Precios aproximados en USD. LLM: (input por 1M tokens, output por 1M tokens).
LLM_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gemini-3.8-flash": (0.075, 0.30),
    "gemini-3.7-flash": (0.075, 0.30),
    "gemini-3.6-flash": (0.075, 0.30),
    "gemini-3.5-flash": (0.075, 0.30),
}

# Imagen: USD por imagen generada.
IMAGE_PRICES: dict[str, float] = {
    "gemini-3.1-flash-image": 0.04,
    "nano-banana": 0.04,
    "fal-ai/flux": 0.025,
}

# Video: USD por segundo generado.
VIDEO_PRICES: dict[str, float] = {
    "gemini-omni": 0.03,
    "fal-ai/kling": 0.05,
    "fal-ai/wan": 0.03,
}

# Video con precio según resolución: USD por segundo.
VIDEO_PRICES_BY_RESOLUTION: dict[str, dict[str, float]] = {
    "gemini-omni": {"360p": 0.03, "720p": 0.10, "1080p": 0.15, "4k": 0.30},
}


def _lookup(table: dict[str, float], model: str) -> float:
    if not model:
        return 0.0
    if model in table:
        return table[model]
    lowered = model.lower()
    for key, value in sorted(table.items(), key=lambda item: len(item[0]), reverse=True):
        if key.lower() in lowered:
            return value
    return 0.0


def video_price(model: str, resolution: str | None = None) -> float:
    lowered = (model or "").lower()
    for key, table in sorted(
        VIDEO_PRICES_BY_RESOLUTION.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if key in lowered:
            if resolution and resolution.lower() in table:
                return table[resolution.lower()]
            return table.get("720p", 0.0)
    return _lookup(VIDEO_PRICES, model)


def model_pricing(kind: str, model: str) -> dict | None:
    """Precio unitario público de un modelo, para estimar antes de generar."""
    if kind == "video":
        for key, table in sorted(
            VIDEO_PRICES_BY_RESOLUTION.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if key in (model or "").lower():
                return {"unit": "second", "usd": table.get("720p", 0.0), "by_resolution": table}
        price = _lookup(VIDEO_PRICES, model)
        return {"unit": "second", "usd": price} if price else None
    if kind == "image":
        price = _lookup(IMAGE_PRICES, model)
        return {"unit": "image", "usd": price} if price else None
    if kind == "llm":
        price = LLM_PRICES.get(model)
        if price is None:
            for key, value in sorted(
                LLM_PRICES.items(), key=lambda item: len(item[0]), reverse=True
            ):
                if key.lower() in (model or "").lower():
                    price = value
                    break
        if price is not None:
            return {"unit": "1m_tokens", "input": price[0], "output": price[1]}
    return None


def estimate_cost(
    kind: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    units: float = 0.0,
    resolution: str | None = None,
) -> float:
    if kind == "llm":
        price = LLM_PRICES.get(model)
        if price is None:
            for key, value in sorted(
                LLM_PRICES.items(), key=lambda item: len(item[0]), reverse=True
            ):
                if key.lower() in (model or "").lower():
                    price = value
                    break
        if price is None:
            return 0.0
        input_price, output_price = price
        return (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    if kind == "image":
        return units * _lookup(IMAGE_PRICES, model)
    if kind == "video":
        return units * video_price(model, resolution)
    return 0.0


def record_api_call(
    session,
    *,
    kind: str,
    provider: str,
    model: str,
    duration_ms: int,
    project_id: int | None = None,
    job_id: int | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    units: float = 0.0,
    resolution: str | None = None,
    status: str = "ok",
    error: str | None = None,
) -> ApiCall:
    call = ApiCall(
        project_id=project_id,
        job_id=job_id,
        kind=kind,
        provider=provider,
        model=model or "",
        status=status,
        duration_ms=max(0, int(duration_ms)),
        input_tokens=max(0, int(input_tokens)),
        output_tokens=max(0, int(output_tokens)),
        units=max(0.0, float(units)),
        cost_usd=estimate_cost(kind, model, input_tokens, output_tokens, units, resolution),
        error=error,
    )
    session.add(call)
    return call
