import { useEffect, useState } from "react";
import { api, fmtDate, isoDate, money } from "../api.js";

export default function StaffDesk() {
  const [on, setOn] = useState(isoDate(new Date()));
  const [all, setAll] = useState(false);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  const load = () =>
    api("/staff/reservations", { params: all ? {} : { on } }).then(setRows).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [on, all]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (id, action) => {
    setError("");
    try {
      await api(action === "checkin" ? `/staff/reservations/${id}/check-in` : `/reservations/${id}/cancel`, { method: "POST" });
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  const active = rows.filter((r) => r.status !== "cancelled");
  const arrivals = active.filter((r) => r.check_in === on && r.status === "booked").length;
  const inHouse = active.filter((r) => r.status === "checked_in").length;

  return (
    <section>
      <div className="card searchbar">
        <label>Date<input type="date" value={on} disabled={all} onChange={(e) => setOn(e.target.value)} /></label>
        <label className="check"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Show all reservations</label>
      </div>
      {!all && (
        <div className="stats">
          <div className="card stat"><span>{arrivals}</span>Arrivals pending</div>
          <div className="card stat"><span>{inHouse}</span>Checked in</div>
          <div className="card stat"><span>{active.length}</span>Rooms occupied</div>
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <div className="card table-wrap">
        <table>
          <thead>
            <tr><th>#</th><th>Guest</th><th>Room</th><th>Stay</th><th>Total</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan="7" className="muted">No reservations.</td></tr>}
            {rows.map((r) => (
              <tr key={r.id} className={r.status}>
                <td>{r.id}</td>
                <td>{r.guest_name}<div className="muted small">{r.guest_email}</div></td>
                <td>{r.room_number}<div className="muted small">{r.room_type}</div></td>
                <td>{fmtDate(r.check_in)} → {fmtDate(r.check_out)}</td>
                <td>{money(r.total_price)}</td>
                <td><span className={`status ${r.status}`}>{r.status.replace("_", " ")}</span></td>
                <td className="row-actions">
                  {r.status === "booked" && <div>
                    <button className="primary sm" onClick={() => act(r.id, "checkin")}>Check in</button>
                    <button className="ghost sm danger" onClick={() => act(r.id, "cancel")}>Cancel</button>
                  </div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
