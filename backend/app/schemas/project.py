from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str
    synopsis: str = ""
    video_style: str = ""
    aspect_ratio: str = "16:9"


class ProjectUpdate(BaseModel):
    name: str | None = None
    synopsis: str | None = None
    video_style: str | None = None
    aspect_ratio: str | None = None
    status: str | None = None
    settings: dict | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    synopsis: str
    video_style: str
    aspect_ratio: str
    status: str
    settings: dict
    created_at: datetime
    updated_at: datetime


class EpisodeUpdate(BaseModel):
    title: str | None = None
    script: dict | None = None
    status: str | None = None


class DialogueLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fragment_id: int
    character_variant_id: int | None
    text: str
    order: int


class FragmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    episode_id: int
    shot_number: int
    time_place: str
    cast: list
    prompt_video: str
    duration: int
    status: str
    video_path: str | None
    dialogue_lines: list[DialogueLineRead] = Field(default_factory=list)


class FragmentUpdate(BaseModel):
    shot_number: int | None = None
    time_place: str | None = None
    cast: list | None = None
    prompt_video: str | None = None
    duration: int | None = None
    status: str | None = None
    video_path: str | None = None


class DialogueLineWrite(BaseModel):
    id: int | None = None
    character_variant_id: int | None = None
    text: str
    order: int = 0


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    number: int
    title: str
    script: dict
    status: str
    fragments: list[FragmentRead] = Field(default_factory=list)
