"""The core guarantee: no double-booking, even when many requests arrive at the same instant."""
import threading
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Reservation, ReservationStatus, Room
from app import services

from .conftest import make_user

CHECK_IN = date.today() + timedelta(days=30)
CHECK_OUT = CHECK_IN + timedelta(days=3)


def _race(user_ids, room_type_id, check_in=CHECK_IN, check_out=CHECK_OUT):
    """Fire one booking per user, all released at the same moment by a barrier."""
    barrier = threading.Barrier(len(user_ids))
    results = []
    lock = threading.Lock()

    def worker(uid):
        s = SessionLocal()
        try:
            user = s.get(services.User, uid)
            barrier.wait()
            services.create_reservation(s, user, room_type_id, check_in, check_out)
            outcome = "ok"
        except services.BookingError:
            outcome = "rejected"
        finally:
            s.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def _guests(db, n):
    return [make_user(db, f"guest{i}@test.dev").id for i in range(n)]


def test_25_guests_race_for_the_last_suite_exactly_one_wins(db, hotel):
    results = _race(_guests(db, 25), hotel["suite"])
    assert results.count("ok") == 1
    assert results.count("rejected") == 24
    assert db.scalar(select(func.count(Reservation.id))) == 1


def test_race_for_3_rooms_books_each_room_once(db, hotel):
    results = _race(_guests(db, 20), hotel["standard"])
    assert results.count("ok") == 3
    room_ids = list(db.scalars(select(Reservation.room_id)))
    assert len(room_ids) == len(set(room_ids)) == 3


def test_overlapping_but_not_identical_dates_still_conflict(db, hotel):
    a, b = _guests(db, 2)
    services.create_reservation(db, db.get(services.User, a), hotel["suite"], CHECK_IN, CHECK_OUT)
    with pytest.raises(services.BookingError):
        services.create_reservation(db, db.get(services.User, b), hotel["suite"],
                                    CHECK_IN + timedelta(days=2), CHECK_OUT + timedelta(days=2))


def test_back_to_back_stays_are_allowed(db, hotel):
    """Checking out on the day the next guest checks in is not an overlap."""
    a, b = _guests(db, 2)
    services.create_reservation(db, db.get(services.User, a), hotel["suite"], CHECK_IN, CHECK_OUT)
    services.create_reservation(db, db.get(services.User, b), hotel["suite"], CHECK_OUT,
                                CHECK_OUT + timedelta(days=2))
    assert db.scalar(select(func.count(Reservation.id))) == 2


def test_cancelled_room_can_be_rebooked(db, hotel):
    a, b = _guests(db, 2)
    res = services.create_reservation(db, db.get(services.User, a), hotel["suite"], CHECK_IN, CHECK_OUT)
    services.cancel_reservation(db, res)
    services.create_reservation(db, db.get(services.User, b), hotel["suite"], CHECK_IN, CHECK_OUT)


def test_database_constraint_blocks_overlap_even_if_app_logic_is_bypassed(db, hotel):
    """Insert directly, skipping the service layer entirely: PostgreSQL itself must refuse."""
    (uid,) = _guests(db, 1)
    room = db.scalar(select(Room).where(Room.room_type_id == hotel["suite"]))
    db.add(Reservation(user_id=uid, room_id=room.id, check_in=CHECK_IN, check_out=CHECK_OUT, total_price=1))
    db.commit()
    db.add(Reservation(user_id=uid, room_id=room.id, check_in=CHECK_IN + timedelta(days=1),
                       check_out=CHECK_OUT + timedelta(days=1), total_price=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # ...but a cancelled reservation does not block the dates.
    db.add(Reservation(user_id=uid, room_id=room.id, check_in=CHECK_IN, check_out=CHECK_OUT,
                       total_price=1, status=ReservationStatus.cancelled))
    db.commit()
