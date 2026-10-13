from datetime import date, timedelta

from app.models import Role
from app.services import nightly_price, stay_price

from .conftest import login, make_user

D1 = date.today() + timedelta(days=14)
D2 = D1 + timedelta(days=2)


def _book(client, headers, room_type_id, ci=D1, co=D2, guests=1):
    return client.post("/api/reservations", headers=headers, json={
        "room_type_id": room_type_id, "check_in": ci.isoformat(), "check_out": co.isoformat(), "guests": guests})


# ---------- auth ----------

def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"email": "New@Test.dev", "full_name": "New", "password": "longenough"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "guest"
    h = login(client, "new@test.dev", "longenough")
    assert client.get("/api/auth/me", headers=h).json()["email"] == "new@test.dev"


def test_duplicate_email_rejected(client):
    body = {"email": "a@test.dev", "full_name": "A", "password": "longenough"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_cannot_self_register_as_staff(client):
    r = client.post("/api/auth/register", json={"email": "x@test.dev", "full_name": "X",
                                                "password": "longenough", "role": "staff"})
    assert r.json()["user"]["role"] == "guest"


def test_bad_password_and_unknown_email_look_identical(client, db):
    make_user(db, "a@test.dev")
    r1 = client.post("/api/auth/login", json={"email": "a@test.dev", "password": "wrong-password"})
    r2 = client.post("/api/auth/login", json={"email": "nobody@test.dev", "password": "wrong-password"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_protected_routes_need_a_valid_token(client, hotel):
    assert client.get("/api/reservations/me").status_code == 401
    assert client.get("/api/reservations/me", headers={"Authorization": "Bearer forged.token.here"}).status_code == 401


# ---------- search & pricing ----------

def test_weekend_pricing():
    fri = date(2026, 10, 16)
    assert nightly_price(100, fri) == 120.0
    assert nightly_price(100, fri + timedelta(days=2)) == 100.0  # Sunday
    assert stay_price(100, fri, fri + timedelta(days=3)) == 340.0  # Fri + Sat + Sun


def test_search_counts_and_filters(client, db, hotel):
    r = client.get("/api/rooms/search", params={"check_in": D1, "check_out": D2})
    by_name = {x["name"]: x for x in r.json()}
    assert by_name["Standard"]["available_rooms"] == 3 and by_name["Suite"]["available_rooms"] == 1
    r = client.get("/api/rooms/search", params={"check_in": D1, "check_out": D2, "guests": 3})
    assert [x["name"] for x in r.json()] == ["Suite"]
    r = client.get("/api/rooms/search", params={"check_in": D1, "check_out": D2, "max_price": 150})
    assert [x["name"] for x in r.json()] == ["Standard"]


def test_search_reflects_bookings(client, db, hotel):
    make_user(db, "g@test.dev")
    _book(client, login(client, "g@test.dev"), hotel["suite"])
    r = client.get("/api/rooms/search", params={"check_in": D1, "check_out": D2})
    assert "Suite" not in [x["name"] for x in r.json()]


def test_search_rejects_bad_dates(client, hotel):
    assert client.get("/api/rooms/search", params={"check_in": D2, "check_out": D1}).status_code == 422


def test_calendar(client, db, hotel):
    make_user(db, "g@test.dev")
    _book(client, login(client, "g@test.dev"), hotel["standard"])
    cal = client.get("/api/rooms/calendar", params={"room_type_id": hotel["standard"], "start": D1, "days": 4}).json()
    assert [d["available_rooms"] for d in cal] == [2, 2, 3, 3]


# ---------- booking ----------

def test_booking_validations(client, db, hotel):
    make_user(db, "g@test.dev")
    h = login(client, "g@test.dev")
    assert _book(client, h, hotel["standard"], guests=3).status_code == 422          # over capacity
    past = date.today() - timedelta(days=3)
    assert _book(client, h, hotel["standard"], past, past + timedelta(days=1)).status_code == 422
    assert _book(client, h, 9999).status_code == 404


def test_guest_cannot_cancel_someone_elses_reservation(client, db, hotel):
    make_user(db, "a@test.dev")
    make_user(db, "b@test.dev")
    res_id = _book(client, login(client, "a@test.dev"), hotel["standard"]).json()["id"]
    r = client.post(f"/api/reservations/{res_id}/cancel", headers=login(client, "b@test.dev"))
    assert r.status_code == 404


# ---------- loyalty ----------

def test_points_earned_and_reversed_on_cancel(client, db, hotel):
    make_user(db, "g@test.dev")
    h = login(client, "g@test.dev")
    res = _book(client, h, hotel["suite"]).json()
    expected = int(res["total_price"] * 10)
    assert client.get("/api/loyalty/me", headers=h).json()["balance"] == expected
    client.post(f"/api/reservations/{res['id']}/cancel", headers=h)
    loyalty = client.get("/api/loyalty/me", headers=h).json()
    assert loyalty["balance"] == 0
    assert [t["points"] for t in loyalty["transactions"]] == [-expected, expected]


def test_tier_progression(client, db, hotel):
    make_user(db, "g@test.dev")
    h = login(client, "g@test.dev")
    # A 5-night suite stay is $1,500+ = 15,000+ points -> Silver
    _book(client, h, hotel["suite"], D1, D1 + timedelta(days=5))
    loyalty = client.get("/api/loyalty/me", headers=h).json()
    assert loyalty["tier"] == "Silver" and loyalty["next_tier"] == "Gold"
    assert loyalty["points_to_next_tier"] == 25_000 - loyalty["balance"]


# ---------- staff / RBAC ----------

def test_staff_routes_forbidden_to_guests(client, db, hotel):
    make_user(db, "g@test.dev")
    h = login(client, "g@test.dev")
    assert client.get("/api/staff/reservations", headers=h).status_code == 403


def test_staff_can_view_check_in_and_cancel(client, db, hotel):
    make_user(db, "g@test.dev")
    make_user(db, "s@test.dev", role=Role.staff)
    g, s = login(client, "g@test.dev"), login(client, "s@test.dev")
    a = _book(client, g, hotel["standard"]).json()["id"]
    b = _book(client, g, hotel["suite"]).json()["id"]
    rows = client.get("/api/staff/reservations", headers=s, params={"on": D1}).json()
    assert {r["id"] for r in rows} == {a, b}
    assert client.post(f"/api/staff/reservations/{a}/check-in", headers=s).json()["status"] == "checked_in"
    assert client.post(f"/api/reservations/{a}/cancel", headers=g).status_code == 409   # already checked in
    assert client.post(f"/api/reservations/{b}/cancel", headers=s).json()["status"] == "cancelled"
