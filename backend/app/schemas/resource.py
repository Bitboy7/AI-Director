from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.resource import ImageOrigin, ResourceType


class ResourceCreate(BaseModel):
    type: ResourceType
    name: str
    profile: dict = Field(default_factory=dict)


class ResourceVariantCreate(BaseModel):
    name: str
    description: str = ""
    episodes: list[int] = Field(default_factory=list)
    image_model: str = ""
    image_style: str = ""
    voice: dict = Field(default_factory=dict)


class ResourceVariantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    episodes: list[int] | None = None
    image_model: str | None = None
    image_style: str | None = None
    voice: dict | None = None


class ReferenceImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    path: str
    origin: ImageOrigin
    kind: str
    created_at: datetime


class ResourceVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    name: str
    description: str
    episodes: list
    image_model: str
    image_style: str
    voice: dict
    reference_images: list[ReferenceImageRead] = Field(default_factory=list)


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    type: ResourceType
    name: str
    profile: dict
    variants: list[ResourceVariantRead] = Field(default_factory=list)
