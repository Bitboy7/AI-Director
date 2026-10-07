from app.services.styles import list_styles, style_prompt


async def test_styles_endpoint_returns_catalog(client):
    r = await client.get("/api/v1/styles")
    assert r.status_code == 200
    styles = r.json()["styles"]
    assert len(styles) >= 6
    assert all("id" in s and "label" in s for s in styles)
    ids = {s["id"] for s in styles}
    assert {"anime", "cinematic", "cyberpunk"}.issubset(ids)


def test_style_prompt_resolves_known_id():
    prompt = style_prompt("anime")
    assert prompt
    assert "anime" in prompt.lower()
    assert prompt != "anime"


def test_style_prompt_returns_raw_for_unknown():
    assert style_prompt("mi estilo libre") == "mi estilo libre"


def test_style_prompt_empty():
    assert style_prompt(None) == ""
    assert style_prompt("") == ""


def test_styles_have_unique_ids():
    ids = [style.id for style in list_styles()]
    assert len(ids) == len(set(ids))
