import enum

from sqlalchemy import JSON, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin


class AssetKind(enum.Enum):
    image = "image"
    video = "video"
    audio = "audio"
    episode = "episode"
    upload = "upload"


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    kind: Mapped[AssetKind] = mapped_column(Enum(AssetKind, native_enum=False))
    path: Mapped[str] = mapped_column(String(500))
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
