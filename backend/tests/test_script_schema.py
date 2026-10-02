import json

from app.schemas.script import ScriptDraft, planned_fragments


def test_script_draft_parses_minimal_json():
    data = {
        "synopsis": "Una historia",
        "characters": [{"name": "Kai", "description": "joven", "tags": ["hero"]}],
        "scenes": [{"name": "Calle", "description": "nocturna", "tags": []}],
        "props": [],
        "episodes": [
            {
                "number": 1,
                "title": "Ep1",
                "shots": [
                    {
                        "shot_number": 1,
                        "time_place": "Calle, noche",
                        "cast": ["Kai"],
                        "action": "Kai camina",
                        "dialogues": [{"character": "Kai", "text": "Hola"}],
                    }
                ],
            }
        ],
    }
    draft = ScriptDraft.model_validate_json(json.dumps(data))
    assert draft.synopsis == "Una historia"
    assert draft.episodes[0].shots[0].dialogues[0].text == "Hola"


def test_planned_fragments():
    assert planned_fragments(90) == 9
    assert planned_fragments(100) == 10
