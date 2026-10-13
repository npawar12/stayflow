"""Load demo data:  python -m app.seed

Creates 4 room types across 3 floors (30 rooms), one staff account, and one guest account.
Safe to run more than once.
"""
from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import Role, Room, RoomType, User
from .security import hash_password

ROOM_TYPES = [
    # name, description, base price, capacity, how many rooms
    ("Standard Queen", "One queen bed, city view, work desk.", 159, 2, 12),
    ("Deluxe King", "One king bed, larger room, skyline view.", 219, 2, 10),
    ("Family Double", "Two queen beds and a sofa bed.", 249, 5, 6),
    ("Executive Suite", "Separate living room, club lounge access.", 429, 4, 2),
]

DEMO_USERS = [
    ("staff@stayflow.dev", "Front Desk", "staffpass123", Role.staff),
    ("guest@stayflow.dev", "Demo Guest", "guestpass123", Role.guest),
]


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.scalar(select(RoomType.id).limit(1)) is None:
            n = 0
            for name, desc, price, cap, count in ROOM_TYPES:
                rt = RoomType(name=name, description=desc, base_price=price, capacity=cap)
                db.add(rt)
                db.flush()
                for _ in range(count):
                    floor = 2 + n // 10
                    db.add(Room(number=f"{floor}{n % 10 + 1:02d}", floor=floor, room_type_id=rt.id))
                    n += 1
        for email, name, pw, role in DEMO_USERS:
            if db.scalar(select(User.id).where(User.email == email)) is None:
                db.add(User(email=email, full_name=name, password_hash=hash_password(pw), role=role))
        db.commit()
        print("Seeded demo data.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
