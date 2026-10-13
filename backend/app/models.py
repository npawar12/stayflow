"""Database schema (normalized: users, room types, physical rooms, reservations, loyalty ledger)."""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Numeric,
                        String, Text, func, text)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Role(str, enum.Enum):
    guest = "guest"
    staff = "staff"


class ReservationStatus(str, enum.Enum):
    booked = "booked"
    checked_in = "checked_in"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.guest)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")


class RoomType(Base):
    __tablename__ = "room_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    base_price: Mapped[float] = mapped_column(Numeric(10, 2))
    capacity: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("base_price > 0"), CheckConstraint("capacity > 0"))

    rooms: Mapped[list["Room"]] = relationship(back_populates="room_type")


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(10), unique=True)
    floor: Mapped[int] = mapped_column(Integer)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), index=True)

    room_type: Mapped[RoomType] = relationship(back_populates="rooms")


class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    guests: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status"), default=ReservationStatus.booked)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="reservations")
    room: Mapped[Room] = relationship()

    __table_args__ = (
        CheckConstraint("check_out > check_in", name="valid_stay"),
        # Defense in depth: even if application code had a bug, PostgreSQL itself refuses
        # two active reservations for the same room with overlapping dates.
        ExcludeConstraint(
            ("room_id", "="),
            (text("daterange(check_in, check_out, '[)')"), "&&"),
            name="no_overlapping_reservations",
            using="gist",
            where=text("status <> 'cancelled'"),
        ),
    )


class LoyaltyTransaction(Base):
    """Append-only ledger. A member's balance is the sum of their rows, so every point
    earned or reversed is auditable."""
    __tablename__ = "loyalty_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"))
    points: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
