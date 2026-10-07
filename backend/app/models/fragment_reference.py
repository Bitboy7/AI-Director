from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin
from app.models.resource import ImageOrigin


class FragmentReferenceImage(TimestampMixin, Base):
    __tablename__ = "fragment_reference_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    fragment_id: Mapped[int] = mapped_column(ForeignKey("fragments.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(500))
    origin: Mapped[ImageOrigin] = mapped_column(
        Enum(ImageOrigin, native_enum=False), default=ImageOrigin.uploaded
    )

    fragment: Mapped["Fragment"] = relationship(back_populates="reference_images")


from app.models.project import Fragment
