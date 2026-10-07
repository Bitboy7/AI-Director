import json

import httpx
import pytest

from app.providers.llm.ollama import OllamaLLM
from app.schemas.script import ScriptGenerationRequest
from app.services.scripting import (
    ScriptValidationError,
    build_system_prompt,
    build_user_prompt,
    generate_script_draft,
    parse_script_json,
)

VALID_DRAFT = {
    "synopsis": "x",
    "characters": [{"name": "Kai", "description": "", "tags": []}],
    "scenes": [],
    "props": [],
    "episodes": [
        {
            "number": 1,
            "title": "t",
            "shots": [
                {
                    "shot_number": 1,
                    "time_place": "",
                    "cast": [],
                    "action": "",
                    "dialogues": [{"character": "Kai", "text": "hola"}],
                }
            ],
        }
    ],
}


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    async def complete(self, system, user, json_mode=False):
        self.calls += 1
        self.prompts.append(user)
        return self.responses.pop(0)


def test_parse_script_json_with_fences():
    draft = parse_script_json("```json\n" + json.dumps(VALID_DRAFT) + "\n```")
    assert draft.synopsis == "x"


async def test_generate_script_draft_success():
    provider = FakeProvider(["not json at all", json.dumps(VALID_DRAFT)])
    req = ScriptGenerationRequest(synopsis="historia")
    draft = await generate_script_draft(provider, req, retries=1)
    assert draft.episodes[0].shots[0].dialogues[0].text == "hola"
    assert provider.calls == 2


async def test_generate_script_draft_exhausts_retries():
    provider = FakeProvider(["nope", "still nope"])
    req = ScriptGenerationRequest(synopsis="historia")
    with pytest.raises(ScriptValidationError):
        await generate_script_draft(provider, req, retries=1)
    assert provider.calls == 2


def test_parse_script_json_empty_raises_clear_error():
    with pytest.raises(ScriptValidationError) as exc_info:
        parse_script_json("   ")
    assert "vacía" in str(exc_info.value)


def test_build_user_prompt_injects_professional_style_prompt():
    req = ScriptGenerationRequest(synopsis="historia", video_style="anime")
    prompt = build_user_prompt(req)
    assert "anime style" in prompt
    assert "Estilo visual: anime style" in prompt


def test_build_user_prompt_keeps_free_text_style():
    req = ScriptGenerationRequest(synopsis="historia", video_style="mi estilo")
    assert "Estilo visual: mi estilo" in build_user_prompt(req)


def test_system_prompt_forbids_mixing_languages():
    prompt = build_system_prompt()
    assert "nunca mezcles" in prompt.lower()
    assert "único idioma" in prompt.lower()


def test_user_prompt_includes_language():
    req = ScriptGenerationRequest(synopsis="x", language="es-MX")
    assert "Idioma: es-MX" in build_user_prompt(req)


async def test_generate_script_retries_with_original_prompt_on_empty_response():
    provider = FakeProvider(["", json.dumps(VALID_DRAFT)])
    req = ScriptGenerationRequest(synopsis="historia")

    draft = await generate_script_draft(provider, req, retries=2)

    assert draft.synopsis == "x"
    assert provider.prompts[0] == build_user_prompt(req)
    assert provider.prompts[1] == build_user_prompt(req)


async def test_generate_script_empty_response_exhausts_retries():
    provider = FakeProvider(["", ""])
    req = ScriptGenerationRequest(synopsis="historia")
    with pytest.raises(ScriptValidationError):
        await generate_script_draft(provider, req, retries=1)


async def test_ollama_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    provider = OllamaLLM(
        base_url="http://localhost:9999", model="test-model", transport=httpx.MockTransport(handler)
    )
    result = await provider.complete("sys", "usr", json_mode=True)
    assert result == "ok"
    assert captured["url"].endswith("/api/chat")
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["format"] == "json"
    assert captured["body"]["stream"] is False
