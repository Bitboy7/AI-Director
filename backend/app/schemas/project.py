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


class DialogueLineWrite(BaseModel):
    id: int | None = None
    character_variant_id: int | None = None
    text: str
    order: int = 0


class EpisodeCreate(BaseModel):
    number: int
    title: str = ""


class FragmentCreate(BaseModel):
    shot_number: int
    time_place: str = ""
    cast: list = Field(default_factory=list)
    prompt_video: str = ""
    duration: int = 10
    dialogues: list[DialogueLineWrite] = Field(default_factory=list)


class DialogueLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fragment_id: int
    character_variant_id: int | None
    text: str
    order: int


class StoryboardPanelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fragment_id: int
    order: int
    title: str
    start_seconds: int
    end_seconds: int
    prompt: str


class StoryboardPanelUpdate(BaseModel):
    title: str | None = None
    start_seconds: int | None = None
    end_seconds: int | None = None
    prompt: str | None = None


class StoryboardPanelCreate(BaseModel):
    title: str = ""
    start_seconds: int = 0
    end_seconds: int = 0
    prompt: str = ""


class FragmentReferenceImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fragment_id: int
    path: str
    origin: str


class FragmentVideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fragment_id: int
    path: str
    provider: str = ""
    model: str = ""
    resolution: str | None = None
    cost_usd: float = 0.0
    created_at: datetime


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
    video_provider: str | None = None
    video_model: str | None = None
    resolution: str | None = None
    cost_usd: float = 0.0
    dialogue_lines: list[DialogueLineRead] = Field(default_factory=list)
    storyboard: list[StoryboardPanelRead] = Field(default_factory=list)
    reference_images: list[FragmentReferenceImageRead] = Field(default_factory=list)
    videos: list[FragmentVideoRead] = Field(default_factory=list)


class FragmentUpdate(BaseModel):
    shot_number: int | None = None
    time_place: str | None = None
    cast: list | None = None
    prompt_video: str | None = None
    duration: int | None = None
    status: str | None = None
    video_path: str | None = None
    video_provider: str | None = None
    video_model: str | None = None
    resolution: str | None = None
    dialogues: list[DialogueLineWrite] | None = None


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    number: int
    title: str
    script: dict
    status: str
    fragments: list[FragmentRead] = Field(default_factory=list)
