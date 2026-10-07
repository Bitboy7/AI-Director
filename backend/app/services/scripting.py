import json

from pydantic import BaseModel, ValidationError

from app.providers.base import LLMProvider
from app.schemas.script import (
    ResourcesDraft,
    ScriptDraft,
    ScriptGenerationRequest,
    StoryboardDraft,
)
from app.services.styles import style_prompt


class ScriptValidationError(ValueError):
    pass


def _schema_json() -> str:
    return json.dumps(ScriptDraft.model_json_schema(), ensure_ascii=False)


def parse_model_json(text: str, model: type[BaseModel]) -> BaseModel:
    cleaned = text.strip()
    if not cleaned:
        raise ScriptValidationError("el LLM devolvió una respuesta vacía")
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ScriptValidationError(
            f"JSON inválido del LLM: {exc}. Respuesta recibida: {cleaned[:200]!r}"
        ) from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ScriptValidationError(f"El JSON no cumple el schema: {exc}") from exc


def build_system_prompt() -> str:
    return (
        "Eres un guionista experto de series cortas de género DRAMA ('Short Drama'). "
        "Debes responder ÚNICAMENTE con un objeto JSON válido que siga exactamente "
        "este JSON Schema (sin markdown, sin comentarios):\n"
        + _schema_json()
        + "\n\nReglas de drama:\n"
        "- La historia gira en torno a un conflicto humano claro con tensión creciente "
        "y un arco emocional (inicio, nudo y desenlace).\n"
        "- 1 personaje principal con un deseo y un obstáculo, y 1-3 secundarios con "
        "descripciones visuales detalladas y motivaciones propias.\n"
        "- Cada capítulo debe terminar en un gancho o giro que empuje a ver el siguiente.\n"
        "- Los diálogos son cortos, naturales y cargados de subtexto emocional.\n"
        "- TODO el texto (sinopsis, descripciones, títulos y diálogos) debe estar en un "
        "ÚNICO idioma y dialecto coherente, el indicado en 'Idioma'; nunca mezcles "
        "idiomas ni acentos regionales.\n"
        "- Cada episodio se descompone en planos (shots) numerados desde 1.\n"
        "- Cada plano dura 10-12 segundos de video: describe una acción breve y concreta.\n"
        "- Un episodio de 90 segundos necesita ~9 planos.\n"
        "- Los diálogos van asociados al nombre del personaje que habla."
    )


def build_user_prompt(req: ScriptGenerationRequest) -> str:
    return (
        f"Sinopsis: {req.synopsis}\n"
        f"Estilo visual: {style_prompt(req.video_style) or 'libre'}\n"
        f"Relación de aspecto: {req.aspect_ratio}\n"
        f"Número de episodios: {req.num_episodes}\n"
        f"Duración por episodio (segundos): {req.episode_duration_seconds}\n"
        f"Idioma: {req.language} (todo el texto debe estar en este idioma, sin mezclar)\n"
        "Genera el guion completo con el desglose de planos."
    )


def parse_script_json(text: str) -> ScriptDraft:
    return parse_model_json(text, ScriptDraft)


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
            if text.strip():
                text = await provider.complete(system, repair_prompt(text, str(exc)), json_mode=True)
            else:
                text = await provider.complete(system, build_user_prompt(req), json_mode=True)
    raise ScriptValidationError("no se pudo generar un guion válido")


def build_resources_system_prompt() -> str:
    return (
        "Eres un diseñador de producción de series cortas. Recibes la sinopsis del "
        "proyecto y los recursos existentes (personajes, escenas, utilería). Debes "
        "responder ÚNICAMENTE con un objeto JSON válido que siga este JSON Schema:\n"
        + json.dumps(ResourcesDraft.model_json_schema(), ensure_ascii=False)
        + "\n\nReglas:\n"
        "- Propón variantes nuevas para recursos existentes (apariencias alternativas) "
        "y recursos nuevos si la historia los necesita.\n"
        "- No repitas variantes cuyo nombre ya existe en el recurso.\n"
        "- Las descripciones deben ser prompts visuales detallados."
    )


def build_resources_user_prompt(script_context: dict) -> str:
    return (
        "Contexto del proyecto:\n"
        + json.dumps(script_context, ensure_ascii=False, indent=2)
        + "\nGenera la lista de recursos con sus variantes."
    )


def parse_resources_json(text: str) -> ResourcesDraft:
    return parse_model_json(text, ResourcesDraft)


async def generate_resources_draft(
    provider: LLMProvider, script_context: dict, retries: int
) -> ResourcesDraft:
    system = build_resources_system_prompt()
    text = await provider.complete(system, build_resources_user_prompt(script_context), json_mode=True)
    for attempt in range(retries + 1):
        try:
            return parse_resources_json(text)
        except ScriptValidationError as exc:
            if attempt >= retries:
                raise
            if text.strip():
                text = await provider.complete(system, repair_prompt(text, str(exc)), json_mode=True)
            else:
                text = await provider.complete(
                    system, build_resources_user_prompt(script_context), json_mode=True
                )
    raise ScriptValidationError("no se pudo generar una lista de recursos válida")


def build_storyboard_system_prompt() -> str:
    return (
        "Eres un director de fotografía de series cortas de drama. Recibes un plano "
        "(fragmento) de 10-12 segundos y debes dividirlo en paneles de storyboard "
        "consecutivos que cubran todo el plano. Responde ÚNICAMENTE con un objeto JSON "
        "válido que siga este JSON Schema:\n"
        + json.dumps(StoryboardDraft.model_json_schema(), ensure_ascii=False)
        +         "\n\nReglas:\n"
        "- Usa 2 a 4 paneles por fragmento, cubriendo de 0 a 12 segundos sin huecos.\n"
        "- Cada panel tiene un título corto, un rango de segundos (start_seconds/end_seconds) "
        "y un prompt visual detallado en inglés listo para un modelo de imagen/video.\n"
        "- Mantén continuidad de personajes, vestuario y escenario entre paneles.\n"
        "- Describe cámara, encuadre, iluminación y acción concreta en cada prompt.\n"
        "- Cuando un panel incluya un personaje, escena o utilería de la lista de recursos "
        "del proyecto, escríbelo en el prompt con la mención exacta @Nombre tal cual "
        "aparece en la lista (por ejemplo @Valeria Cruz), sin traducir ni alterar el "
        "nombre. Usa @ únicamente para nombres que existan en la lista de recursos.\n"
        "- Las menciones @Nombre permiten al pipeline adjuntar las imágenes de referencia "
        "de cada recurso, así que repítelas en todos los paneles donde el recurso aparezca."
    )


def build_storyboard_user_prompt(context: dict) -> str:
    return (
        "Fragmento:\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + "\nGenera los paneles del storyboard para este fragmento."
    )


async def generate_storyboard_draft(
    provider: LLMProvider, context: dict, retries: int
) -> StoryboardDraft:
    system = build_storyboard_system_prompt()
    text = await provider.complete(system, build_storyboard_user_prompt(context), json_mode=True)
    for attempt in range(retries + 1):
        try:
            return parse_model_json(text, StoryboardDraft)
        except ScriptValidationError as exc:
            if attempt >= retries:
                raise
            if text.strip():
                text = await provider.complete(system, repair_prompt(text, str(exc)), json_mode=True)
            else:
                text = await provider.complete(
                    system, build_storyboard_user_prompt(context), json_mode=True
                )
    raise ScriptValidationError("no se pudo generar un storyboard válido")
