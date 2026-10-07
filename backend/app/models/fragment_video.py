from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class FragmentVideo(TimestampMixin, Base):
    __tablename__ = "fragment_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    fragment_id: Mapped[int] = mapped_column(ForeignKey("fragments.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(500))
    provider: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    resolution: Mapped[str | None] = mapped_column(String(50), default=None)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    fragment: Mapped["Fragment"] = relationship(back_populates="videos")


from app.models.project import Fragment
