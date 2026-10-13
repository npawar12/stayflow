import { useEffect, useState } from "react";
import { api, fmtDate, isoDate, money } from "../api.js";

export default function MyStays() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const load = () => api("/reservations/me").then(setRows).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const cancel = async (id) => {
    if (!window.confirm("Cancel this reservation? The points you earned for it will be removed.")) return;
    try {
      await api(`/reservations/${id}/cancel`, { method: "POST" });
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  if (!rows) return <div className="muted">Loading…</div>;
  const today = isoDate(new Date());
  const upcoming = rows.filter((r) => r.status !== "cancelled" && r.check_out >= today);
  const other = rows.filter((r) => !upcoming.includes(r));

  const Row = ({ r }) => (
    <div className={`card stay ${r.status}`}>
      <div>
        <h3>{r.room_type} · Room {r.room_number}</h3>
        <p className="muted">{fmtDate(r.check_in)} → {fmtDate(r.check_out)} · {r.guests} guest{r.guests > 1 && "s"}</p>
      </div>
      <div className="stay-right">
        <span className={`status ${r.status}`}>{r.status.replace("_", " ")}</span>
        <strong>{money(r.total_price)}</strong>
        {r.status === "booked" && <button className="ghost danger" onClick={() => cancel(r.id)}>Cancel</button>}
      </div>
    </div>
  );

  return (
    <section>
      {error && <div className="error">{error}</div>}
      <h2>Upcoming</h2>
      {upcoming.length ? upcoming.map((r) => <Row key={r.id} r={r} />) : <p className="muted">No upcoming stays yet.</p>}
      {other.length > 0 && <><h2>Past &amp; cancelled</h2>{other.map((r) => <Row key={r.id} r={r} />)}</>}
    </section>
  );
}
