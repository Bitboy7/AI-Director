from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    synopsis: Mapped[str] = mapped_column(Text, default="")
    video_style: Mapped[str] = mapped_column(String(200), default="")
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9")
    status: Mapped[str] = mapped_column(String(30), default="draft")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    resources: Mapped[list["Resource"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )


class Episode(TimestampMixin, Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300), default="")
    script: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="draft")

    project: Mapped[Project] = relationship(back_populates="episodes")
    fragments: Mapped[list["Fragment"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan", lazy="selectin"
    )


class Fragment(TimestampMixin, Base):
    __tablename__ = "fragments"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    shot_number: Mapped[int] = mapped_column(Integer)
    time_place: Mapped[str] = mapped_column(String(300), default="")
    cast: Mapped[list] = mapped_column(JSON, default=list)
    prompt_video: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    video_path: Mapped[str | None] = mapped_column(String(500), default=None)

    episode: Mapped[Episode] = relationship(back_populates="fragments")
    dialogue_lines: Mapped[list["DialogueLine"]] = relationship(
        back_populates="fragment", cascade="all, delete-orphan", lazy="selectin"
    )


class DialogueLine(TimestampMixin, Base):
    __tablename__ = "dialogue_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    fragment_id: Mapped[int] = mapped_column(ForeignKey("fragments.id", ondelete="CASCADE"))
    character_variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("resource_variants.id", ondelete="SET NULL"), default=None
    )
    text: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)

    fragment: Mapped[Fragment] = relationship(back_populates="dialogue_lines")
