import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import Dashboard from "./pages/Dashboard.jsx";
import Reportes from "./pages/Reportes.jsx";
import Admin from "./pages/Admin.jsx";

function Login({ onLogin }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  async function entrar(e) {
    e.preventDefault();
    try {
      const r = await api("/auth/login", { method: "POST", form: { username: u, password: p } });
      setToken(r.access_token);
      onLogin(r.usuario);
    } catch (x) { setErr(x.message); }
  }
  return (
    <form className="panel login" onSubmit={entrar}>
      <h2 style={{ color: "#f59e0b" }}>NOC — Monitoreo Proactivo</h2>
      <p className="d">Ingresa con tu cuenta (RBAC + JWT)</p>
      <label>Usuario</label><input value={u} onChange={(e) => setU(e.target.value)} autoFocus />
      <label>Contraseña</label><input type="password" value={p} onChange={(e) => setP(e.target.value)} />
      {err && <div className="err">{err}</div>}
      <div className="row"><button className="btn am" type="submit">Ingresar</button></div>
    </form>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [cargando, setCargando] = useState(!!getToken());
  const [tab, setTab] = useState("dashboard");

  useEffect(() => {
    if (getToken()) api("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setCargando(false));
    const salir = () => setUser(null);
    window.addEventListener("sesion-expirada", salir);
    return () => window.removeEventListener("sesion-expirada", salir);
  }, []);

  if (cargando) return null;
  if (!user) return <div className="wrap"><Login onLogin={setUser} /></div>;

  const can = (p) => user.permisos.includes(p);
  const tabs = [["dashboard", "Dashboard"], can("VER_REPORTES") && ["reportes", "Reportes SLA"],
    (can("CONFIG_UMBRALES") || can("GESTIONAR_USUARIOS")) && ["admin", "Administración"]].filter(Boolean);

  return (
    <div className="wrap">
      <div className="bar">
        <div>
          <h1>NOC — MONITOREO PROACTIVO Y ALERTA TEMPRANA</h1>
          <div className="sub mut">{user.username} · {user.rol}</div>
        </div>
        <div className="tabs">
          {tabs.map(([k, n]) => <button key={k} className={"tab" + (tab === k ? " on" : "")} onClick={() => setTab(k)}>{n}</button>)}
          <button className="btn" onClick={() => { setToken(null); setUser(null); }}>Salir</button>
        </div>
      </div>
      {tab === "dashboard" && <Dashboard can={can} />}
      {tab === "reportes" && <Reportes />}
      {tab === "admin" && <Admin can={can} />}
    </div>
  );
}
