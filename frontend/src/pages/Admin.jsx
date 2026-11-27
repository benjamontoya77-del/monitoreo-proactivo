import { useCallback, useEffect, useState } from "react";
import { api, fmtFecha } from "../api";

// "disponibilidad" no se ofrece aquí: se crea sola con cada nodo (alerta crítica si no responde)
const PARAMS = ["latencia_ms", "uso_cpu_pct", "uso_ram_pct", "interfaces_down"];
const DEFECTO = { latencia_ms: 150, uso_cpu_pct: 85, uso_ram_pct: 90, interfaces_down: 0 };
const AYUDA = {
  latencia_ms: "Milisegundos. Alerta si el ping supera este valor.",
  uso_cpu_pct: "Porcentaje (0 a 100). Requiere SNMP activado en el nodo.",
  uso_ram_pct: "Porcentaje (0 a 100). Requiere SNMP activado en el nodo.",
  interfaces_down: "Cantidad de interfaces caídas (0 = alerta con la primera). Requiere SNMP.",
};

function Umbrales() {
  const [nodos, setNodos] = useState([]);
  const [reglas, setReglas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errCarga, setErrCarga] = useState("");
  const [f, setF] = useState({ dispositivo_id: "", parametro: "latencia_ms", valor_umbral: 150, criticidad: "Alta" });
  const [err, setErr] = useState("");

  const cargar = useCallback(async () => {
    try {
      const [n, r] = await Promise.all([api("/dispositivos"), api("/umbrales")]);
      setNodos(n); setReglas(r); setErrCarga("");
    } catch (x) { setErrCarga(x.message); }
    finally { setCargando(false); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const nombre = (id) => nodos.find((n) => n.id === id)?.nombre ?? `#${id}`;
  const sinNodos = !cargando && !errCarga && nodos.length === 0;

  function validar() {
    if (!f.dispositivo_id) return "Selecciona un nodo.";
    const v = Number(f.valor_umbral);
    if (f.valor_umbral === "" || !Number.isFinite(v)) return "El umbral debe ser un número.";
    if (v < 0) return "El umbral no puede ser negativo.";
    if ((f.parametro === "uso_cpu_pct" || f.parametro === "uso_ram_pct") && v > 100)
      return "Para CPU y RAM el umbral es un porcentaje: debe estar entre 0 y 100.";
    return "";
  }
  const problema = validar();

  async function crear() {
    try {
      await api("/umbrales", { method: "POST", body: { ...f, dispositivo_id: Number(f.dispositivo_id), valor_umbral: Number(f.valor_umbral) } });
      setErr(""); cargar();
    } catch (x) { setErr(x.message); }
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const cambiarParametro = (e) => setF({ ...f, parametro: e.target.value, valor_umbral: DEFECTO[e.target.value] });

  return (
    <div className="panel">
      <h2>Umbrales de alerta temprana</h2>
      <p className="d">Una alerta se dispara cuando el valor medido supera el umbral. La alerta de disponibilidad (nodo que no responde) se crea sola con cada nodo.</p>

      {errCarga && <div className="err">No se pudieron cargar los datos: {errCarga}</div>}
      {sinNodos && (
        <div className="aviso">
          No hay nodos registrados, por eso la lista de nodos y la tabla están vacías. Ve a <b>Dashboard → + Nuevo nodo</b>,
          registra uno y vuelve aquí: aparecerá en la lista y ya tendrá su regla de disponibilidad.
        </div>
      )}

      <div className="form-inline">
        <div><label>Nodo</label>
          <select value={f.dispositivo_id} onChange={set("dispositivo_id")} disabled={sinNodos}>
            <option value="">{sinNodos ? "Sin nodos registrados" : "Seleccionar…"}</option>
            {nodos.map((n) => <option key={n.id} value={n.id}>{n.nombre} ({n.ip})</option>)}
          </select></div>
        <div><label>Parámetro</label><select value={f.parametro} onChange={cambiarParametro}>{PARAMS.map((p) => <option key={p}>{p}</option>)}</select></div>
        <div><label>Umbral</label><input type="number" min="0" value={f.valor_umbral} onChange={set("valor_umbral")} /></div>
        <div><label>Criticidad</label><select value={f.criticidad} onChange={set("criticidad")}><option>Alta</option><option>Crítica</option></select></div>
        <button className="btn am" disabled={!!problema} title={problema} onClick={crear}>+ Agregar</button>
      </div>
      <div className="hint">{AYUDA[f.parametro]}{f.dispositivo_id && problema ? ` · ${problema}` : ""}</div>
      {err && <div className="err">{err}</div>}

      <div className="tbl-wrap"><table>
        <thead><tr><th>Nodo</th><th>Parámetro</th><th>Umbral</th><th>Criticidad</th><th>Habilitada</th><th /></tr></thead>
        <tbody>
          {reglas.length === 0 && <tr><td colSpan={6} className="mut">{cargando ? "Cargando…" : "Aún no hay reglas."}</td></tr>}
          {reglas.map((r) => (
            <tr key={r.id}><td>{nombre(r.dispositivo_id)}</td><td>{r.parametro}</td><td>{r.valor_umbral}</td>
              <td className={r.criticidad === "Crítica" ? "crit" : "warn"}>{r.criticidad}</td>
              <td><input type="checkbox" checked={r.habilitada} onChange={async (e) => { await api(`/umbrales/${r.id}`, { method: "PUT", body: { habilitada: e.target.checked } }); cargar(); }} /></td>
              <td><button className="btn rd" title="Eliminar (borra también el historial de alertas de esta regla; para conservarlo, desactívala)"
                onClick={async () => { if (confirm("¿Eliminar la regla y TODO su historial de alertas? Para conservarlo, desactívala en su lugar.")) { await api(`/umbrales/${r.id}`, { method: "DELETE" }); cargar(); } }}>🗑️</button></td></tr>))}
        </tbody>
      </table></div>
    </div>
  );
}

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function Usuarios() {
  const [us, setUs] = useState([]);
  const [roles, setRoles] = useState([]);
  const [f, setF] = useState({ username: "", email: "", password: "", rol_id: "" });
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [creando, setCreando] = useState(false);

  const cargar = useCallback(async () => { setUs(await api("/usuarios")); setRoles(await api("/roles")); }, []);
  useEffect(() => { cargar(); }, [cargar]);
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setOk(""); setErr(""); };

  function validar() {
    const userNorm = f.username.trim().toLowerCase();
    const emailNorm = f.email.trim().toLowerCase();
    if (userNorm.length < 3) return "El usuario debe tener al menos 3 caracteres.";
    if (us.some((u) => u.username.toLowerCase() === userNorm))
      return `No se puede registrar: el usuario "${f.username.trim()}" ya está registrado.`;
    if (!EMAIL_RE.test(emailNorm)) return "Escribe un correo válido (ej.: nombre@empresa.cl).";
    if (us.some((u) => u.email.toLowerCase() === emailNorm))
      return `No se puede registrar: el correo "${emailNorm}" ya está registrado en otro usuario.`;
    if (f.password.length < 8) return "La contraseña debe tener al menos 8 caracteres.";
    if (!f.rol_id) return "Selecciona un rol.";
    return "";
  }
  const problema = validar();
  const tocado = f.username || f.email || f.password;

  async function crear() {
    const msgError = validar();
    if (msgError) {
      setErr(msgError);
      setOk("");
      return;
    }

    setCreando(true);
    setErr("");
    setOk("");
    try {
      const username = f.username.trim();
      const email = f.email.trim().toLowerCase();
      await api("/usuarios", { method: "POST", body: { ...f, username, email, rol_id: Number(f.rol_id) } });
      setOk(`Usuario ${username} creado correctamente y notificación enviada a ${email}.`);
      setF({ username: "", email: "", password: "", rol_id: "" });
      await cargar();
    } catch (x) {
      setErr(x.message || "No se pudo registrar el usuario.");
    } finally {
      setCreando(false);
    }
  }

  async function eliminar(u) {
    if (!confirm(`¿Eliminar definitivamente al usuario "${u.username}" (${u.email})? Si solo quieres suspenderlo temporalmente, desmarca la casilla Activo.`)) return;
    try {
      await api(`/usuarios/${u.id}`, { method: "DELETE" });
      setErr(""); setOk(`Usuario ${u.username} eliminado.`);
      cargar();
    } catch (x) { setErr(x.message); setOk(""); }
  }

  return (
    <div className="panel">
      <h2>Usuarios y roles (RBAC)</h2><p className="d">Contraseñas mínimo 8 caracteres · almacenadas con bcrypt</p>
      <div className="form-inline">
        <div><label>Usuario</label><input value={f.username} onChange={set("username")} placeholder="tecnico1" /></div>
        <div><label>Correo</label><input value={f.email} onChange={set("email")} placeholder="tecnico1@empresa.cl" /></div>
        <div><label>Contraseña</label><input type="password" value={f.password} onChange={set("password")} autoComplete="new-password" /></div>
        <div><label>Rol</label><select value={f.rol_id} onChange={set("rol_id")}><option value="">Seleccionar…</option>{roles.map((r) => <option key={r.id} value={r.id}>{r.nombre_rol}</option>)}</select></div>
        <button className="btn am" disabled={creando} onClick={crear}>{creando ? "Registrando…" : "+ Crear"}</button>
      </div>
      {tocado && problema && !err && <div className="hint">{problema}</div>}
      {err && <div className="err">{err}</div>}
      {ok && <div className="ok" style={{ fontSize: 12, marginTop: 8 }}>{ok}</div>}
      <div className="tbl-wrap"><table>
        <thead><tr><th>Usuario</th><th>Correo</th><th>Rol</th><th>Activo</th><th /></tr></thead>
        <tbody>{us.map((u) => (
          <tr key={u.id}><td><b>{u.username}</b></td><td className="mut">{u.email}</td><td>{u.rol}</td>
            <td><input type="checkbox" disabled={u.username.toLowerCase() === "admin"} checked={u.activo} onChange={async (e) => { try { await api(`/usuarios/${u.id}`, { method: "PATCH", body: { activo: e.target.checked } }); cargar(); } catch (x) { setErr(x.message); } }} /></td>
            <td>{u.username.toLowerCase() !== "admin" && (
              <button className="btn rd" title="Eliminar usuario definitivamente" onClick={() => eliminar(u)}>🗑️</button>
            )}</td></tr>))}</tbody>
      </table></div>
    </div>
  );
}

function Auditoria() {
  const [a, setA] = useState([]);
  useEffect(() => { api("/auditoria").then(setA).catch(() => {}); }, []);
  return (
    <div className="panel">
      <h2>Auditoría de acceso</h2><p className="d">Inicios de sesión (exitosos y fallidos) y cambios de configuración</p>
      <div className="tbl-wrap" style={{ maxHeight: 340, overflowY: "auto" }}><table>
        <thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Detalle</th><th>IP origen</th></tr></thead>
        <tbody>{a.map((x) => <tr key={x.id}><td>{fmtFecha(x.fecha)}</td><td>{x.username}</td><td className={x.accion === "LOGIN_FALLIDO" ? "crit" : ""}>{x.accion}</td><td className="mut">{x.detalle}</td><td className="mut">{x.ip_origen}</td></tr>)}</tbody>
      </table></div>
    </div>
  );
}

export default function Admin({ can }) {
  return (<>{can("CONFIG_UMBRALES") && <Umbrales />}{can("GESTIONAR_USUARIOS") && <><Usuarios /><Auditoria /></>}</>);
}