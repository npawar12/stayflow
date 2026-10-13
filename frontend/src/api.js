// Small fetch wrapper: attaches the JWT and turns API errors into readable messages.
const TOKEN_KEY = "stayflow_token";

export const auth = {
  get token() {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set token(v) {
    try { v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY); } catch {}
  },
};

export async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL(`/api${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) url.searchParams.set(k, v);
    });
  }
  const headers = { "Content-Type": "application/json" };
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    let msg = data?.detail ?? `Request failed (${res.status})`;
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg.replace(/^Value error, /, "")).join("; ");
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const money = (n) =>
  Number(n).toLocaleString("en-US", { style: "currency", currency: "USD" });

export const fmtDate = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

export const isoDate = (d) => {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 10);
};

export const addDays = (iso, n) => {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return isoDate(d);
};
