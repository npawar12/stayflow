import { useEffect, useState } from "react";
import { addDays, api, isoDate, money } from "../api.js";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// Month grid showing how many rooms of one type are free each night.
export default function Calendar({ roomTypeId, selected, onPick }) {
  const today = isoDate(new Date());
  const [month, setMonth] = useState(() => (selected?.[0] ?? today).slice(0, 7) + "-01");
  const [days, setDays] = useState([]);

  useEffect(() => {
    const first = new Date(month + "T00:00:00");
    const len = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
    api("/rooms/calendar", { params: { room_type_id: roomTypeId, start: month, days: len } }).then(setDays);
  }, [roomTypeId, month]);

  const shift = (n) => {
    const d = new Date(month + "T00:00:00");
    d.setMonth(d.getMonth() + n);
    setMonth(isoDate(d).slice(0, 7) + "-01");
  };

  const lead = new Date(month + "T00:00:00").getDay();
  const label = new Date(month + "T00:00:00").toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const [ci, co] = selected ?? [];

  return (
    <div className="calendar">
      <div className="cal-head">
        <button className="ghost sm" onClick={() => shift(-1)} disabled={month <= today.slice(0, 7) + "-01"}>‹</button>
        <strong>{label}</strong>
        <button className="ghost sm" onClick={() => shift(1)}>›</button>
      </div>
      <div className="cal-grid">
        {WEEKDAYS.map((w) => <div key={w} className="dow">{w}</div>)}
        {Array.from({ length: lead }).map((_, i) => <div key={"e" + i} />)}
        {days.map((d) => {
          const past = d.date < today;
          const full = d.available_rooms === 0;
          const inStay = ci && d.date >= ci && d.date < co;
          const cls = ["day", past && "past", full && "full", !full && d.available_rooms <= 2 && "low", inStay && "sel"]
            .filter(Boolean).join(" ");
          return (
            <button key={d.date} className={cls} disabled={past || full} onClick={() => onPick(d.date)}
              title={`${d.available_rooms}/${d.total_rooms} free · ${money(d.nightly_price)}`}>
              <span className="num">{Number(d.date.slice(8))}</span>
              <span className="avail">{full ? "Full" : `${d.available_rooms} free`}</span>
              <span className="rate">${Math.round(d.nightly_price)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

