"""Business logic, kept out of the route handlers so it can be tested directly
(including from many threads at once in the concurrency tests)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import POINTS_PER_DOLLAR, TIERS, WEEKEND_MULTIPLIER
from .models import (LoyaltyTransaction, Reservation, ReservationStatus, Room, RoomType, User)


class BookingError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


# ---------- pricing ----------

def nightly_price(base: float, night: date) -> float:
    """Friday and Saturday nights cost more, like most hotels."""
    return round(float(base) * (WEEKEND_MULTIPLIER if night.weekday() in (4, 5) else 1.0), 2)


def stay_price(base: float, check_in: date, check_out: date) -> float:
    nights = (check_out - check_in).days
    return round(sum(nightly_price(base, check_in + timedelta(days=i)) for i in range(nights)), 2)


def points_for(amount: float) -> int:
    return int(amount * POINTS_PER_DOLLAR)


# ---------- availability ----------

def _overlaps(check_in: date, check_out: date):
    """Two stays overlap when each starts before the other ends. Check-out day is free
    for the next guest, so the comparisons are strict."""
    return and_(
        Reservation.status != ReservationStatus.cancelled,
        Reservation.check_in < check_out,
        Reservation.check_out > check_in,
    )


def available_room_ids(db: Session, room_type_id: int, check_in: date, check_out: date) -> list[int]:
    busy = select(Reservation.room_id).where(_overlaps(check_in, check_out))
    q = (select(Room.id).where(Room.room_type_id == room_type_id, Room.id.not_in(busy))
         .order_by(Room.id))
    return list(db.scalars(q))


def search(db: Session, check_in: date, check_out: date, guests: int = 1,
           min_price: float | None = None, max_price: float | None = None,
           room_type_id: int | None = None) -> list[dict]:
    busy = select(Reservation.room_id).where(_overlaps(check_in, check_out))
    q = (select(RoomType, func.count(Room.id))
         .join(Room, Room.room_type_id == RoomType.id)
         .where(Room.id.not_in(busy), RoomType.capacity >= guests)
         .group_by(RoomType.id)
         .order_by(RoomType.base_price))
    if min_price is not None:
        q = q.where(RoomType.base_price >= min_price)
    if max_price is not None:
        q = q.where(RoomType.base_price <= max_price)
    if room_type_id is not None:
        q = q.where(RoomType.id == room_type_id)
    nights = (check_out - check_in).days
    out = []
    for rt, count in db.execute(q):
        total = stay_price(rt.base_price, check_in, check_out)
        out.append({
            "room_type_id": rt.id, "name": rt.name, "description": rt.description,
            "capacity": rt.capacity, "base_price": float(rt.base_price),
            "available_rooms": count, "nights": nights, "total_price": total,
            "points_to_earn": points_for(total),
        })
    return out


def calendar(db: Session, room_type_id: int, start: date, days: int) -> list[dict]:
    """Rooms of a type still free on each night in [start, start + days)."""
    rt = db.get(RoomType, room_type_id)
    if rt is None:
        raise BookingError("Room type not found", 404)
    total = db.scalar(select(func.count(Room.id)).where(Room.room_type_id == room_type_id))
    end = start + timedelta(days=days)
    rows = db.execute(
        select(Reservation.check_in, Reservation.check_out)
        .join(Room, Room.id == Reservation.room_id)
        .where(Room.room_type_id == room_type_id, _overlaps(start, end))
    ).all()
    booked = [0] * days
    for ci, co in rows:
        for i in range(max((ci - start).days, 0), min((co - start).days, days)):
            booked[i] += 1
    return [{"date": start + timedelta(days=i), "available_rooms": total - booked[i],
             "total_rooms": total, "nightly_price": nightly_price(rt.base_price, start + timedelta(days=i))}
            for i in range(days)]


# ---------- booking ----------

def create_reservation(db: Session, user: User, room_type_id: int, check_in: date,
                       check_out: date, guests: int = 1) -> Reservation:
    """Book any free room of the requested type, safely under concurrency.

    1. SELECT ... FOR UPDATE locks every room row of this type. A second request for the
       same type blocks here until the first transaction commits or rolls back, so two
       requests can never both see the same room as free.
    2. With the lock held, find a free room and insert the reservation.
    3. The exclusion constraint on the table is a second, database-level guarantee.
    """
    if check_in < date.today():
        raise BookingError("Cannot book a stay in the past", 422)
    rt = db.get(RoomType, room_type_id)
    if rt is None:
        raise BookingError("Room type not found", 404)
    if guests > rt.capacity:
        raise BookingError(f"{rt.name} holds at most {rt.capacity} guests", 422)
    try:
        db.execute(select(Room.id).where(Room.room_type_id == room_type_id)
                   .order_by(Room.id).with_for_update())
        free = available_room_ids(db, room_type_id, check_in, check_out)
        if not free:
            raise BookingError("No rooms of this type are available for those dates")
        total = stay_price(rt.base_price, check_in, check_out)
        res = Reservation(user_id=user.id, room_id=free[0], check_in=check_in,
                          check_out=check_out, guests=guests, total_price=total)
        db.add(res)
        db.flush()
        db.add(LoyaltyTransaction(user_id=user.id, reservation_id=res.id, points=points_for(total),
                                  reason=f"Stay {check_in:%b %d}–{check_out:%b %d}, {rt.name}"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BookingError("That room was just booked by someone else; please try again")
    except BookingError:
        db.rollback()
        raise
    db.refresh(res)
    return res


def cancel_reservation(db: Session, res: Reservation) -> Reservation:
    if res.status == ReservationStatus.cancelled:
        raise BookingError("Reservation is already cancelled")
    if res.status == ReservationStatus.checked_in:
        raise BookingError("Guest has already checked in")
    res.status = ReservationStatus.cancelled
    earned = db.scalar(select(func.coalesce(func.sum(LoyaltyTransaction.points), 0))
                       .where(LoyaltyTransaction.reservation_id == res.id))
    if earned:
        db.add(LoyaltyTransaction(user_id=res.user_id, reservation_id=res.id, points=-earned,
                                  reason=f"Cancelled reservation #{res.id}"))
    db.commit()
    db.refresh(res)
    return res


def check_in_reservation(db: Session, res: Reservation) -> Reservation:
    if res.status != ReservationStatus.booked:
        raise BookingError(f"Cannot check in a reservation that is {res.status.value}")
    res.status = ReservationStatus.checked_in
    db.commit()
    db.refresh(res)
    return res


# ---------- loyalty ----------

def loyalty_summary(db: Session, user: User) -> dict:
    txs = list(db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.user_id == user.id)
                          .order_by(LoyaltyTransaction.created_at.desc(), LoyaltyTransaction.id.desc())))
    balance = sum(t.points for t in txs)
    # Tier is based on points actually kept (earned minus reversals).
    lifetime = max(balance, 0)
    tier = next(name for floor, name in TIERS if lifetime >= floor)
    higher = [(floor, name) for floor, name in reversed(TIERS) if floor > lifetime]
    nxt = higher[0] if higher else None
    return {"balance": balance, "lifetime_points": lifetime, "tier": tier,
            "next_tier": nxt[1] if nxt else None,
            "points_to_next_tier": (nxt[0] - lifetime) if nxt else None,
            "transactions": txs}


def to_out(res: Reservation) -> dict:
    return {"id": res.id, "room_number": res.room.number, "room_type": res.room.room_type.name,
            "check_in": res.check_in, "check_out": res.check_out, "guests": res.guests,
            "status": res.status.value, "total_price": float(res.total_price),
            "guest_name": res.user.full_name, "guest_email": res.user.email,
            "created_at": res.created_at}
