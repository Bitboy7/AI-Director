import math

from pydantic import BaseModel, Field


class ScriptGenerationRequest(BaseModel):
    synopsis: str
    video_style: str = ""
    aspect_ratio: str = "16:9"
    num_episodes: int = 1
    episode_duration_seconds: int = 90
    language: str = "es"


class ScriptResource(BaseModel):
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class ScriptCharacter(ScriptResource):
    pass


class ScriptScene(ScriptResource):
    pass


class ScriptProp(ScriptResource):
    pass


class ScriptDialogue(BaseModel):
    character: str
    text: str


class ScriptShot(BaseModel):
    shot_number: int
    time_place: str = ""
    cast: list[str] = Field(default_factory=list)
    action: str = ""
    dialogues: list[ScriptDialogue] = Field(default_factory=list)


class ScriptEpisode(BaseModel):
    number: int
    title: str
    shots: list[ScriptShot] = Field(default_factory=list)


class ScriptDraft(BaseModel):
    synopsis: str = ""
    characters: list[ScriptCharacter] = Field(default_factory=list)
    scenes: list[ScriptScene] = Field(default_factory=list)
    props: list[ScriptProp] = Field(default_factory=list)
    episodes: list[ScriptEpisode] = Field(default_factory=list)


def planned_fragments(duration_seconds: int, fragment_seconds: int = 10) -> int:
    return math.ceil(duration_seconds / fragment_seconds)
