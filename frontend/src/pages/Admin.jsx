import { useCallback, useEffect, useState } from "react";
import { api, fmtFecha } from "../api";

const PARAMS = ["latencia_ms", "uso_cpu_pct", "uso_ram_pct", "interfaces_down", "disponibilidad"];

function Umbrales() {
  const [nodos, setNodos] = useState([]);
  const [reglas, setReglas] = useState([]);
  const [f, setF] = useState({ dispositivo_id: "", parametro: "latencia_ms", valor_umbral: 150, criticidad: "Alta" });
  const [err, setErr] = useState("");
  const cargar = useCallback(async () => { setNodos(await api("/dispositivos")); setReglas(await api("/umbrales")); }, []);
  useEffect(() => { cargar(); }, [cargar]);
  const nombre = (id) => nodos.find((n) => n.id === id)?.nombre ?? id;

  async function crear() {
    try {
      await api("/umbrales", { method: "POST", body: { ...f, dispositivo_id: Number(f.dispositivo_id), valor_umbral: Number(f.valor_umbral) } });
      setErr(""); cargar();
    } catch (x) { setErr(x.message); }
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="panel">
      <h2>Umbrales de alerta temprana</h2><p className="d">Una alerta se dispara cuando el valor medido supera el umbral (disponibilidad: cuando el nodo no responde)</p>
      <div className="form-inline">
        <div><label>Nodo</label><select value={f.dispositivo_id} onChange={set("dispositivo_id")}><option value="">Seleccionar…</option>{nodos.map((n) => <option key={n.id} value={n.id}>{n.nombre}</option>)}</select></div>
        <div><label>Parámetro</label><select value={f.parametro} onChange={set("parametro")}>{PARAMS.map((p) => <option key={p}>{p}</option>)}</select></div>
        <div><label>Umbral</label><input type="number" value={f.valor_umbral} onChange={set("valor_umbral")} /></div>
        <div><label>Criticidad</label><select value={f.criticidad} onChange={set("criticidad")}><option>Alta</option><option>Crítica</option></select></div>
        <button className="btn am" disabled={!f.dispositivo_id} onClick={crear}>+ Agregar</button>
      </div>
      {err && <div className="err">{err}</div>}
      <div className="tbl-wrap"><table>
        <thead><tr><th>Nodo</th><th>Parámetro</th><th>Umbral</th><th>Criticidad</th><th>Habilitada</th><th /></tr></thead>
        <tbody>{reglas.map((r) => (
          <tr key={r.id}><td>{nombre(r.dispositivo_id)}</td><td>{r.parametro}</td><td>{r.valor_umbral}</td><td className={r.criticidad === "Crítica" ? "crit" : "warn"}>{r.criticidad}</td>
            <td><input type="checkbox" checked={r.habilitada} onChange={async (e) => { await api(`/umbrales/${r.id}`, { method: "PUT", body: { habilitada: e.target.checked } }); cargar(); }} /></td>
            <td><button className="btn rd" onClick={async () => { await api(`/umbrales/${r.id}`, { method: "DELETE" }); cargar(); }}>🗑️</button></td></tr>))}</tbody>
      </table></div>
    </div>
  );
}

function Usuarios() {
  const [us, setUs] = useState([]);
  const [roles, setRoles] = useState([]);
  const [f, setF] = useState({ username: "", email: "", password: "", rol_id: "" });
  const [err, setErr] = useState("");
  const cargar = useCallback(async () => { setUs(await api("/usuarios")); setRoles(await api("/roles")); }, []);
  useEffect(() => { cargar(); }, [cargar]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function crear() {
    try { await api("/usuarios", { method: "POST", body: { ...f, rol_id: Number(f.rol_id) } }); setErr(""); setF({ username: "", email: "", password: "", rol_id: "" }); cargar(); }
    catch (x) { setErr(x.message); }
  }
  return (
    <div className="panel">
      <h2>Usuarios y roles (RBAC)</h2><p className="d">Contraseñas mínimo 8 caracteres · almacenadas con bcrypt</p>
      <div className="form-inline">
        <div><label>Usuario</label><input value={f.username} onChange={set("username")} /></div>
        <div><label>Correo</label><input value={f.email} onChange={set("email")} /></div>
        <div><label>Contraseña</label><input type="password" value={f.password} onChange={set("password")} /></div>
        <div><label>Rol</label><select value={f.rol_id} onChange={set("rol_id")}><option value="">Seleccionar…</option>{roles.map((r) => <option key={r.id} value={r.id}>{r.nombre_rol}</option>)}</select></div>
        <button className="btn am" disabled={!f.rol_id} onClick={crear}>+ Crear</button>
      </div>
      {err && <div className="err">{err}</div>}
      <div className="tbl-wrap"><table>
        <thead><tr><th>Usuario</th><th>Correo</th><th>Rol</th><th>Activo</th></tr></thead>
        <tbody>{us.map((u) => (
          <tr key={u.id}><td><b>{u.username}</b></td><td className="mut">{u.email}</td><td>{u.rol}</td>
            <td><input type="checkbox" checked={u.activo} onChange={async (e) => { try { await api(`/usuarios/${u.id}`, { method: "PATCH", body: { activo: e.target.checked } }); cargar(); } catch (x) { alert(x.message); } }} /></td></tr>))}</tbody>
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
