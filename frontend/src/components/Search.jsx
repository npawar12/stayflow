import { useEffect, useState } from "react";
import { addDays, api, isoDate, money } from "../api.js";
import Calendar from "./Calendar.jsx";

export default function Search({ canBook, onBooked }) {
  const today = isoDate(new Date());
  const [q, setQ] = useState({
    check_in: addDays(today, 7), check_out: addDays(today, 9),
    guests: 2, min_price: "", max_price: "", room_type_id: "",
  });
  const [types, setTypes] = useState([]);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [calType, setCalType] = useState(null);
  const [booking, setBooking] = useState(null);

  useEffect(() => { api("/room-types").then(setTypes); }, []);
  useEffect(() => { run(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setQ({ ...q, [k]: e.target.value });

  async function run(e) {
    e?.preventDefault();
    setError("");
    try {
      setResults(await api("/rooms/search", { params: q }));
    } catch (err) {
      setError(err.message);
      setResults(null);
    }
  }

  async function book(rt) {
    setBooking(rt.room_type_id);
    setError("");
    try {
      const r = await api("/reservations", {
        method: "POST",
        body: { room_type_id: rt.room_type_id, check_in: q.check_in, check_out: q.check_out, guests: Number(q.guests) },
      });
      setMessage(`Booked room ${r.room_number} — ${rt.name}. You earned ${rt.points_to_earn.toLocaleString()} points.`);
      setTimeout(onBooked, 1400);
    } catch (err) {
      setError(err.message);
      run();
    } finally {
      setBooking(null);
    }
  }

  // Picking a night on the calendar starts a 2-night search from that date.
  const pickDate = (iso) => {
    const next = { ...q, check_in: iso, check_out: addDays(iso, 2) };
    setQ(next);
    api("/rooms/search", { params: next }).then(setResults).catch((e) => setError(e.message));
  };

  return (
    <section>
      <form className="card searchbar" onSubmit={run}>
        <label>Check in<input type="date" min={today} value={q.check_in} onChange={set("check_in")} /></label>
        <label>Check out<input type="date" min={addDays(q.check_in, 1)} value={q.check_out} onChange={set("check_out")} /></label>
        <label>Guests<input type="number" min="1" max="10" value={q.guests} onChange={set("guests")} /></label>
        <label>Room type
          <select value={q.room_type_id} onChange={set("room_type_id")}>
            <option value="">Any</option>
            {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label>Min $/night<input type="number" min="0" placeholder="—" value={q.min_price} onChange={set("min_price")} /></label>
        <label>Max $/night<input type="number" min="0" placeholder="—" value={q.max_price} onChange={set("max_price")} /></label>
        <button className="primary">Search</button>
      </form>

      {message && <div className="success">{message}</div>}
      {error && <div className="error">{error}</div>}

      {results && results.length === 0 && (
        <div className="card empty">No rooms match those dates and filters. Try the calendar to find open nights.</div>
      )}

      <div className="results">
        {results?.map((rt) => (
          <article className="card room" key={rt.room_type_id}>
            <div className="room-head">
              <h3>{rt.name}</h3>
              <span className={rt.available_rooms <= 2 ? "left low" : "left"}>
                {rt.available_rooms} left
              </span>
            </div>
            <p className="muted">{rt.description}</p>
            <p className="meta">Sleeps {rt.capacity} · from {money(rt.base_price)}/night</p>
            <div className="room-foot">
              <div>
                <div className="price">{money(rt.total_price)}</div>
                <div className="muted small">{rt.nights} night{rt.nights > 1 && "s"} · +{rt.points_to_earn.toLocaleString()} pts</div>
              </div>
              <div className="actions">
                <button className="ghost" onClick={() => setCalType(calType === rt.room_type_id ? null : rt.room_type_id)}>
                  {calType === rt.room_type_id ? "Hide calendar" : "Calendar"}
                </button>
                {canBook && (
                  <button className="primary" disabled={booking !== null} onClick={() => book(rt)}>
                    {booking === rt.room_type_id ? "Booking…" : "Book"}
                  </button>
                )}
              </div>
            </div>
            {calType === rt.room_type_id && (
              <Calendar roomTypeId={rt.room_type_id} selected={[q.check_in, q.check_out]} onPick={pickDate} />
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
