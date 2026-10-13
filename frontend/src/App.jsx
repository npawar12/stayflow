import { useEffect, useState } from "react";
import { api, auth } from "./api.js";
import AuthForm from "./components/AuthForm.jsx";
import Search from "./components/Search.jsx";
import MyStays from "./components/MyStays.jsx";
import Rewards from "./components/Rewards.jsx";
import StaffDesk from "./components/StaffDesk.jsx";

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(auth.token));
  const [tab, setTab] = useState("search");

  useEffect(() => {
    if (!auth.token) return;
    api("/auth/me")
      .then(setUser)
      .catch(() => (auth.token = null))
      .finally(() => setLoading(false));
  }, []);

  const onAuth = ({ access_token, user }) => {
    auth.token = access_token;
    setUser(user);
    setTab(user.role === "staff" ? "staff" : "search");
  };
  const logout = () => {
    auth.token = null;
    setUser(null);
  };

  if (loading) return <div className="center muted">Loading…</div>;
  if (!user) return <AuthForm onAuth={onAuth} />;

  const tabs = user.role === "staff"
    ? [["staff", "Front desk"], ["search", "Availability"]]
    : [["search", "Book a stay"], ["stays", "My stays"], ["rewards", "Rewards"]];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">Stay<span>Flow</span></div>
        <nav>
          {tabs.map(([id, label]) => (
            <button key={id} className={tab === id ? "tab active" : "tab"} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="who">
          <span>{user.full_name}{user.role === "staff" && <em className="badge">staff</em>}</span>
          <button className="link" onClick={logout}>Sign out</button>
        </div>
      </header>
      <main>
        {tab === "search" && <Search canBook={user.role === "guest"} onBooked={() => setTab("stays")} />}
        {tab === "stays" && <MyStays />}
        {tab === "rewards" && <Rewards />}
        {tab === "staff" && <StaffDesk />}
      </main>
    </div>
  );
}
