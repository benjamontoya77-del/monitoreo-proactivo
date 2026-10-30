const BASE = import.meta.env.VITE_API_URL || "/api";

export const getToken = () => localStorage.getItem("token");
export const setToken = (t) => (t ? localStorage.setItem("token", t) : localStorage.removeItem("token"));

export async function api(path, { method = "GET", body, form, blob } = {}) {
  const headers = {};
  if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
  let payload;
  if (form) payload = new URLSearchParams(form);
  else if (body) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const res = await fetch(BASE + path, { method, headers, body: payload });
  if (res.status === 401 && path !== "/auth/login") {
    setToken(null);
    window.dispatchEvent(new Event("sesion-expirada"));
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = await res.json();
      msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch { /* sin cuerpo */ }
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return blob ? res.blob() : res.json();
}

export const fmtDur = (s) => {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
  return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
};
// El backend guarda UTC sin zona: se agrega "Z" para mostrar la hora local correcta.
export const fmtFecha = (iso) =>
  iso ? new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z").toLocaleString("es-CL") : "—";