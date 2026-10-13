import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres@localhost:5432/stayflow_test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, Room, RoomType, User  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    init_db()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE loyalty_transactions, reservations, rooms, room_types, users "
                          "RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def hotel(db):
    """Two room types: 'Standard' with 3 rooms, 'Suite' with exactly 1 room."""
    std = RoomType(name="Standard", description="", base_price=100, capacity=2)
    suite = RoomType(name="Suite", description="", base_price=300, capacity=4)
    db.add_all([std, suite])
    db.flush()
    db.add_all([Room(number=f"10{i}", floor=1, room_type_id=std.id) for i in range(1, 4)])
    db.add(Room(number="201", floor=2, room_type_id=suite.id))
    db.commit()
    return {"standard": std.id, "suite": suite.id}


@pytest.fixture
def client():
    return TestClient(app)


def make_user(db, email, role=Role.guest, password="password123"):
    u = User(email=email, full_name=email.split("@")[0].title(), password_hash=hash_password(password), role=role)
    db.add(u)
    db.commit()
    return u


def login(client, email, password="password123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
