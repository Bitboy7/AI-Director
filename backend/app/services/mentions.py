import re

_MENTION = "@"


def extract_mentions(text: str, names: list[str]) -> list[str]:
    """Devuelve los nombres de recursos mencionados con @ en el texto.

    Coincide el nombre más largo primero para que '@Valeria Cruz' no se confunda
    con '@Valeria'. Ignora mayúsculas/minúsculas y conserva el orden de aparición.
    """
    if not text or not names:
        return []
    ordered = sorted({name for name in names if name}, key=len, reverse=True)
    found: list[tuple[int, str]] = []
    used_spans: list[tuple[int, int]] = []
    lowered = text.lower()
    for name in ordered:
        pattern = re.compile(re.escape(_MENTION + name.lower()))
        for match in pattern.finditer(lowered):
            start, end = match.span()
            if any(s < end and start < e for s, e in used_spans):
                continue
            used_spans.append((start, end))
            found.append((start, name))
    found.sort(key=lambda item: item[0])
    return [name for _, name in found]
