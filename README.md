# StayFlow

A full-stack hotel reservation platform: guests search availability, book rooms, and earn loyalty points; front-desk staff manage arrivals. Built with **FastAPI**, **PostgreSQL**, and **React**.

The interesting engineering problem is **preventing double-booking when many guests try to book the last room at the same instant** — see [How double-booking is prevented](#how-double-booking-is-prevented).

## Features

**Guests**
- Search by dates, party size, room type, and nightly price range
- Month-view availability calendar per room type (rooms left each night, weekend pricing)
- Book, view upcoming/past stays, cancel
- Loyalty dashboard: points balance, tier (Member → Silver → Gold → Platinum), progress to next tier, full points history

**Front-desk staff**
- Daily view of arrivals and in-house guests, or all reservations
- Check guests in; cancel on a guest's behalf

**Security**
- Passwords hashed with bcrypt; stateless JWT authentication
- Role-based access control: staff endpoints return 403 to guests; guests can only see or cancel their own reservations (others' return 404, so IDs can't be probed)
- Self-registration can only create guest accounts
- Login returns the same error for unknown email and wrong password, so the API doesn't reveal which emails are registered

## Architecture

```
React (Vite)  ──HTTP/JSON + JWT──▶  FastAPI  ──SQLAlchemy──▶  PostgreSQL
                                     routes.py   -> HTTP, auth, validation
                                     services.py -> booking, pricing, loyalty logic
                                     models.py   -> schema + constraints
```

**Schema** (normalized): `users`, `room_types` (price, capacity), `rooms` (physical room → type), `reservations` (room, dates, status, price), `loyalty_transactions` (append-only points ledger — balance is the sum of a member's rows, so every point earned or reversed is auditable).

## How double-booking is prevented

Two layers:

1. **Row-level locking in the application.** Booking runs in one transaction that first does `SELECT … FROM rooms WHERE room_type_id = ? FOR UPDATE`. A second request for the same room type blocks on that lock until the first commits, then sees the first booking when it looks for a free room. Requests for *different* room types don't block each other.

2. **A PostgreSQL exclusion constraint** as a database-level guarantee:
   ```sql
   EXCLUDE USING gist (room_id WITH =, daterange(check_in, check_out, '[)') WITH &&)
   WHERE (status <> 'cancelled')
   ```
   PostgreSQL itself rejects two active reservations for the same room with overlapping dates, even if a future code change forgot the lock. The half-open range `[)` means checking out on the 5th and someone checking in on the 5th is allowed.

**Why both?** I tested what happens with the lock removed. The constraint still prevented every double-booking, but when 20 guests raced for 3 rooms, they all picked the same "first free" room, one won, and the rest were rejected — **only 2 of 3 rooms got booked even though a room was still free**. The lock makes concurrent bookers queue up so each one sees an accurate picture; the constraint is the safety net.

The tests in `backend/tests/test_concurrency.py` release 25 threads simultaneously (with a `threading.Barrier`) at the last suite and assert exactly one succeeds, and release 20 threads at 3 rooms and assert exactly 3 distinct rooms are booked.

## Running locally

**With Docker (one command):**
```bash
docker compose up --build
# open http://localhost:8000
```

**Without Docker:**
```bash
# 1. PostgreSQL running locally with a database named "stayflow"
cd backend
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://postgres@localhost:5432/stayflow
python -m app.seed                      # 30 rooms across 4 room types + demo accounts
uvicorn app.main:app --reload --port 8000

# 2. In another terminal
cd frontend
npm install
npm run dev                             # http://localhost:5173 (proxies /api to :8000)
```

Demo accounts (buttons on the login page fill these in):
- Guest: `guest@stayflow.dev` / `guestpass123`
- Front desk: `staff@stayflow.dev` / `staffpass123`

Interactive API docs: http://localhost:8000/docs

## Tests

```bash
cd backend
createdb stayflow_test
pytest -q          # 22 tests: concurrency, auth, RBAC, search, pricing, loyalty
```

GitHub Actions runs the backend tests against a real PostgreSQL service container, builds the frontend, and builds the Docker image on every push.

## API overview

| Method | Path | Who |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login` | anyone |
| GET | `/api/rooms/search?check_in&check_out&guests&min_price&max_price&room_type_id` | anyone |
| GET | `/api/rooms/calendar?room_type_id&start&days` | anyone |
| POST | `/api/reservations` | guest |
| GET | `/api/reservations/me` | guest |
| POST | `/api/reservations/{id}/cancel` | owner or staff |
| GET | `/api/loyalty/me` | guest |
| GET | `/api/staff/reservations?on=YYYY-MM-DD` | staff |
| POST | `/api/staff/reservations/{id}/check-in` | staff |

## Pricing & loyalty rules

- Friday and Saturday nights are priced at 1.2× the base rate.
- Guests earn 10 points per dollar when they book; cancelling posts a matching negative ledger entry.
- Tiers: Silver at 10,000 points, Gold at 25,000, Platinum at 50,000.
