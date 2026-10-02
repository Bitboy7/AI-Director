import json

from pydantic import ValidationError

from app.providers.base import LLMProvider
from app.schemas.script import ScriptDraft, ScriptGenerationRequest


class ScriptValidationError(ValueError):
    pass


def _schema_json() -> str:
    return json.dumps(ScriptDraft.model_json_schema(), ensure_ascii=False)


def build_system_prompt() -> str:
    return (
        "Eres un guionista de series cortas estilo 'Short Drama'. "
        "Debes responder ÚNICAMENTE con un objeto JSON válido que siga exactamente "
        "este JSON Schema (sin markdown, sin comentarios):\n"
        + _schema_json()
        + "\n\nReglas:\n"
        "- 1 personaje principal y 1-3 secundarios con descripciones visuales detalladas.\n"
        "- Cada episodio se descompone en planos (shots) numerados desde 1.\n"
        "- Cada plano dura 10-12 segundos de video: describe acción breve y diálogos cortos.\n"
        "- Un episodio de 90 segundos necesita ~9 planos.\n"
        "- Los diálogos van asociados al nombre del personaje que habla."
    )


def build_user_prompt(req: ScriptGenerationRequest) -> str:
    return (
        f"Sinopsis: {req.synopsis}\n"
        f"Estilo visual: {req.video_style or 'libre'}\n"
        f"Relación de aspecto: {req.aspect_ratio}\n"
        f"Número de episodios: {req.num_episodes}\n"
        f"Duración por episodio (segundos): {req.episode_duration_seconds}\n"
        f"Idioma: {req.language}\n"
        "Genera el guion completo con el desglose de planos."
    )


def parse_script_json(text: str) -> ScriptDraft:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ScriptValidationError(f"JSON inválido del LLM: {exc}") from exc
    try:
        return ScriptDraft.model_validate(data)
    except ValidationError as exc:
        raise ScriptValidationError(f"El JSON no cumple el schema: {exc}") from exc


def repair_prompt(bad_json: str, error: str) -> str:
    return (
        f"Tu respuesta anterior no era un JSON válido según el schema. Error: {error}\n"
        f"Respuesta incorrecta:\n{bad_json}\n"
        "Corrige los errores y responde SOLO con el JSON válido."
    )


async def generate_script_draft(
    provider: LLMProvider, req: ScriptGenerationRequest, retries: int
) -> ScriptDraft:
    system = build_system_prompt()
    text = await provider.complete(system, build_user_prompt(req), json_mode=True)
    for attempt in range(retries + 1):
        try:
            return parse_script_json(text)
        except ScriptValidationError as exc:
            if attempt >= retries:
                raise
            text = await provider.complete(system, repair_prompt(text, str(exc)), json_mode=True)
    raise ScriptValidationError("no se pudo generar un guion válido")
