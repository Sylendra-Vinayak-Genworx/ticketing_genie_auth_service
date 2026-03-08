from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.constants.enum import ContactMode
from src.data.models.postgres.base import Base, TimestampMixin, UUIDMixin
from src.data.models.postgres.role import Role
from src.data.models.postgres.token import RefreshToken
from src.data.models.postgres.team import Team
from typing import ClassVar


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    lead_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    preferred_mode_of_contact: Mapped[ContactMode] = mapped_column(
        Enum(ContactMode, name="contact_mode_enum",
        values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        server_default=ContactMode.EMAIL.value,
    )

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    role: Mapped[Role] = relationship(
        back_populates="users",
        lazy="joined",
    )
    
    teams: Mapped[list["Team"]] = relationship(
    "Team",
    back_populates="lead",
    foreign_keys="Team.lead_id"
    )

    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
    )

    customer_tierid: Mapped[int] = mapped_column(
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} customer_tierid={self.customer_tierid}>"
