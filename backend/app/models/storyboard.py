from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class StoryboardPanel(TimestampMixin, Base):
    __tablename__ = "storyboard_panels"

    id: Mapped[int] = mapped_column(primary_key=True)
    fragment_id: Mapped[int] = mapped_column(ForeignKey("fragments.id", ondelete="CASCADE"))
    order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200), default="")
    start_seconds: Mapped[int] = mapped_column(Integer, default=0)
    end_seconds: Mapped[int] = mapped_column(Integer, default=0)
    prompt: Mapped[str] = mapped_column(Text, default="")

    fragment: Mapped["Fragment"] = relationship(back_populates="storyboard")


from app.models.project import Fragment
