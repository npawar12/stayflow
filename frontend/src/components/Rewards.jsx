import { useEffect, useState } from "react";
import { api } from "../api.js";

const TIER_FLOORS = { Member: 0, Silver: 10000, Gold: 25000, Platinum: 50000 };

export default function Rewards() {
  const [data, setData] = useState(null);
  useEffect(() => { api("/loyalty/me").then(setData); }, []);
  if (!data) return <div className="muted">Loading…</div>;

  const floor = TIER_FLOORS[data.tier];
  const ceiling = data.next_tier ? TIER_FLOORS[data.next_tier] : floor;
  const pct = data.next_tier ? Math.min(100, ((data.lifetime_points - floor) / (ceiling - floor)) * 100) : 100;

  return (
    <section>
      <div className={`card tier-card tier-${data.tier.toLowerCase()}`}>
        <div className="tier-label">{data.tier}</div>
        <div className="points">{data.balance.toLocaleString()} <span>points</span></div>
        <div className="progress"><div style={{ width: `${pct}%` }} /></div>
        <p>
          {data.next_tier
            ? <>{data.points_to_next_tier.toLocaleString()} points to <strong>{data.next_tier}</strong></>
            : "You've reached our highest tier."}
        </p>
        <p className="small">Earn 10 points per dollar on every stay.</p>
      </div>

      <h2>Activity</h2>
      <div className="card ledger">
        {data.transactions.length === 0 && <p className="muted">Book a stay to start earning.</p>}
        {data.transactions.map((t) => (
          <div className="ledger-row" key={t.id}>
            <div>
              <div>{t.reason}</div>
              <div className="muted small">{new Date(t.created_at).toLocaleString()}</div>
            </div>
            <strong className={t.points < 0 ? "neg" : "pos"}>
              {t.points > 0 ? "+" : ""}{t.points.toLocaleString()}
            </strong>
          </div>
        ))}
      </div>
    </section>
  );
}
