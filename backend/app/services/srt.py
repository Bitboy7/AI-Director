from pydantic import BaseModel


class SrtEntry(BaseModel):
    start_seconds: float
    end_seconds: float
    text: str


def _fmt(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(entries: list[SrtEntry]) -> str:
    blocks = [
        f"{i}\n{_fmt(e.start_seconds)} --> {_fmt(e.end_seconds)}\n{e.text}"
        for i, e in enumerate(entries, 1)
    ]
    return "\n\n".join(blocks) + "\n\n" if blocks else ""
