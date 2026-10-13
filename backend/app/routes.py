from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import services
from .db import get_db
from .models import Reservation, Role, RoomType, User
from .schemas import (DayAvailability, LoginIn, LoyaltyOut, RegisterIn, ReservationIn,
                      ReservationOut, RoomTypeAvailability, StayIn, TokenOut, UserOut)
from .security import create_token, get_current_user, hash_password, require_staff, verify_password

router = APIRouter(prefix="/api")


def _raise(e: services.BookingError):
    raise HTTPException(e.status_code, str(e))


# ---------- auth ----------

@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    # Self-registration always creates a guest. Staff accounts are created by seed/admin only,
    # so nobody can grant themselves staff access.
    user = User(email=body.email, full_name=body.full_name,
                password_hash=hash_password(body.password), role=Role.guest)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with that email already exists")
    db.refresh(user)
    return {"access_token": create_token(user), "user": user}


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    # Same message for "no such user" and "wrong password" so the API doesn't leak which emails exist.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return {"access_token": create_token(user), "user": user}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ---------- rooms ----------

@router.get("/room-types")
def room_types(db: Session = Depends(get_db)):
    return [{"id": rt.id, "name": rt.name, "capacity": rt.capacity, "base_price": float(rt.base_price)}
            for rt in db.scalars(select(RoomType).order_by(RoomType.base_price))]


@router.get("/rooms/search", response_model=list[RoomTypeAvailability])
def search_rooms(check_in: date, check_out: date, guests: int = Query(1, ge=1, le=10),
                 min_price: float | None = Query(None, ge=0), max_price: float | None = Query(None, ge=0),
                 room_type_id: int | None = None, db: Session = Depends(get_db)):
    try:
        StayIn(check_in=check_in, check_out=check_out)
    except ValueError as e:
        raise HTTPException(422, str(e).split("\n")[-1])
    return services.search(db, check_in, check_out, guests, min_price, max_price, room_type_id)


@router.get("/rooms/calendar", response_model=list[DayAvailability])
def room_calendar(room_type_id: int, start: date, days: int = Query(35, ge=1, le=90),
                  db: Session = Depends(get_db)):
    try:
        return services.calendar(db, room_type_id, start, days)
    except services.BookingError as e:
        _raise(e)


# ---------- reservations (guest) ----------

@router.post("/reservations", response_model=ReservationOut, status_code=201)
def book(body: ReservationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        res = services.create_reservation(db, user, body.room_type_id, body.check_in,
                                          body.check_out, body.guests)
    except services.BookingError as e:
        _raise(e)
    return services.to_out(res)


@router.get("/reservations/me", response_model=list[ReservationOut])
def my_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Reservation).where(Reservation.user_id == user.id)
                      .order_by(Reservation.check_in.desc()))
    return [services.to_out(r) for r in rows]


@router.post("/reservations/{res_id}/cancel", response_model=ReservationOut)
def cancel(res_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    res = db.get(Reservation, res_id)
    # Guests may only touch their own reservations; return 404 (not 403) so IDs can't be probed.
    if res is None or (res.user_id != user.id and user.role != Role.staff):
        raise HTTPException(404, "Reservation not found")
    try:
        return services.to_out(services.cancel_reservation(db, res))
    except services.BookingError as e:
        _raise(e)


# ---------- staff ----------

@router.get("/staff/reservations", response_model=list[ReservationOut])
def all_reservations(on: date | None = None, _: User = Depends(require_staff), db: Session = Depends(get_db)):
    q = select(Reservation).order_by(Reservation.check_in, Reservation.id)
    if on is not None:  # everyone in the hotel (or arriving) on that date
        q = q.where(Reservation.check_in <= on, Reservation.check_out > on)
    return [services.to_out(r) for r in db.scalars(q)]


@router.post("/staff/reservations/{res_id}/check-in", response_model=ReservationOut)
def staff_check_in(res_id: int, _: User = Depends(require_staff), db: Session = Depends(get_db)):
    res = db.get(Reservation, res_id)
    if res is None:
        raise HTTPException(404, "Reservation not found")
    try:
        return services.to_out(services.check_in_reservation(db, res))
    except services.BookingError as e:
        _raise(e)


# ---------- loyalty ----------

@router.get("/loyalty/me", response_model=LoyaltyOut)
def loyalty(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return services.loyalty_summary(db, user)
