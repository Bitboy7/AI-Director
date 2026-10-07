from app.services.mentions import extract_mentions


def test_extract_simple_mentions():
    assert extract_mentions("Veo a @Goku correr", ["Goku", "Valeria"]) == ["Goku"]


def test_extract_multiple_in_order():
    text = "@Goku mira a @Valeria y luego a @Goku"
    assert extract_mentions(text, ["Goku", "Valeria"]) == ["Goku", "Valeria", "Goku"]


def test_longest_name_wins():
    text = "Entra @Valeria Cruz en escena"
    assert extract_mentions(text, ["Valeria", "Valeria Cruz"]) == ["Valeria Cruz"]


def test_case_insensitive():
    assert extract_mentions("hola @goku", ["Goku"]) == ["Goku"]


def test_no_mentions():
    assert extract_mentions("sin menciones", ["Goku"]) == []


def test_ignores_unknown_names():
    assert extract_mentions("hola @Desconocido", ["Goku"]) == []
