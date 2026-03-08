from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.constants.enum import UserRole
from src.data.models.postgres.base import Base, TimestampMixin, UUIDMixin


class Role(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        unique=True,
    )

    users = relationship(
        "User",
        back_populates="role",
        cascade="all, delete-orphan",
    )
