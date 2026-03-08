from __future__ import annotations

from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.postgres.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.data.models.postgres.user import User


class Team(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    lead: Mapped["User | None"] = relationship(
        "User",
        back_populates="teams",
        foreign_keys=[lead_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Team id={self.id} name={self.name!r}>"