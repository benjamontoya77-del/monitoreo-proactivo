const BASE = import.meta.env.VITE_API_URL || "/api";

export const getToken = () => localStorage.getItem("token");
export const setToken = (t) => (t ? localStorage.setItem("token", t) : localStorage.removeItem("token"));

// Nombres legibles de los campos para los mensajes de validación
const CAMPOS = {
  username: "Usuario", email: "Correo", password: "Contraseña", rol_id: "Rol", ip: "Dirección IP",
  nombre: "Nombre", frecuencia_segundos: "Frecuencia", url_http: "URL", comunidad_snmp: "Comunidad SNMP",
  valor_umbral: "Umbral", dispositivo_id: "Nodo", parametro: "Parámetro", tipo_dispositivo: "Tipo",
};

function mensajeValidacion(e) {
  const clave = (e.loc || []).slice(-1)[0];
  const campo = CAMPOS[clave] || clave;
  const ctx = e.ctx || {};
  let txt;
  switch (e.type) {
    case "string_too_short": txt = `debe tener al menos ${ctx.min_length} caracteres`; break;
    case "string_too_long": txt = `no puede superar ${ctx.max_length} caracteres`; break;
    case "string_pattern_mismatch": txt = "tiene un formato no válido"; break;
    case "greater_than_equal": txt = `debe ser mayor o igual a ${ctx.ge}`; break;
    case "less_than_equal": txt = `debe ser menor o igual a ${ctx.le}`; break;
    case "missing": txt = "es obligatorio"; break;
    case "value_error": txt = (e.msg || "").replace(/^Value error, /, ""); break;
    default: txt = e.msg;
  }
  return `${campo}: ${txt}`;
}

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
      if (typeof d.detail === "string") msg = d.detail;
      else if (Array.isArray(d.detail)) msg = d.detail.map(mensajeValidacion).join(" · ");
      else msg = JSON.stringify(d.detail);
    } catch { /* sin cuerpo */ }
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return blob ? res.blob() : res.json();
}

// Descarga un archivo generado por la API (con el token de sesión)
export async function descargar(path, nombreArchivo) {
  const b = await api(path, { blob: true });
  const url = URL.createObjectURL(b);
  const a = document.createElement("a");
  a.href = url; a.download = nombreArchivo; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
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