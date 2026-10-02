import enum

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class ResourceType(enum.Enum):
    character = "character"
    scene = "scene"
    prop = "prop"


class ImageOrigin(enum.Enum):
    uploaded = "uploaded"
    generated = "generated"


class Resource(TimestampMixin, Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    type: Mapped[ResourceType] = mapped_column(Enum(ResourceType, native_enum=False))
    name: Mapped[str] = mapped_column(String(200))
    profile: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="resources")
    variants: Mapped[list["ResourceVariant"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan", lazy="selectin"
    )


class ResourceVariant(TimestampMixin, Base):
    __tablename__ = "resource_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    episodes: Mapped[list] = mapped_column(JSON, default=list)
    image_model: Mapped[str] = mapped_column(String(100), default="")
    image_style: Mapped[str] = mapped_column(String(200), default="")
    voice: Mapped[dict] = mapped_column(JSON, default=dict)

    resource: Mapped[Resource] = relationship(back_populates="variants")
    reference_images: Mapped[list["ReferenceImage"]] = relationship(
        back_populates="variant", cascade="all, delete-orphan", lazy="selectin"
    )


class ReferenceImage(TimestampMixin, Base):
    __tablename__ = "reference_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("resource_variants.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(500))
    origin: Mapped[ImageOrigin] = mapped_column(
        Enum(ImageOrigin, native_enum=False), default=ImageOrigin.uploaded
    )
    kind: Mapped[str] = mapped_column(String(30), default="reference")

    variant: Mapped[ResourceVariant] = relationship(back_populates="reference_images")


from app.models.project import Project  # noqa: E402
