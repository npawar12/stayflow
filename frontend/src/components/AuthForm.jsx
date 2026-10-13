import { useState } from "react";
import { api } from "../api.js";

export default function AuthForm({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", full_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body = mode === "login" ? { email: form.email, password: form.password } : form;
      onAuth(await api(`/auth/${mode}`, { method: "POST", body }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const demo = (email, password) => setForm({ ...form, email, password });

  return (
    <div className="auth-wrap">
      <form className="card auth" onSubmit={submit}>
        <div className="brand big">Stay<span>Flow</span></div>
        <p className="muted">{mode === "login" ? "Sign in to book and manage stays." : "Create a guest account."}</p>
        {mode === "register" && (
          <label>Full name<input value={form.full_name} onChange={set("full_name")} required /></label>
        )}
        <label>Email<input type="email" value={form.email} onChange={set("email")} required /></label>
        <label>Password
          <input type="password" value={form.password} onChange={set("password")} minLength={8} required />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={busy}>{busy ? "…" : mode === "login" ? "Sign in" : "Create account"}</button>
        <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}
        </button>
        {mode === "login" && (
          <div className="demo">
            Demo:
            <button type="button" className="chip" onClick={() => demo("guest@stayflow.dev", "guestpass123")}>Guest</button>
            <button type="button" className="chip" onClick={() => demo("staff@stayflow.dev", "staffpass123")}>Front desk</button>
          </div>
        )}
      </form>
    </div>
  );
}
