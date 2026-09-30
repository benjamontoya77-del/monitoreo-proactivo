import { useCallback, useEffect, useState } from "react";
import Chart from "react-apexcharts";
import { api, fmtDur, fmtFecha } from "../api";

const COLORES = { ACTIVO: "ok", ALERTA: "warn", "CRÍTICO": "crit" };
const VACIO = { tipo_dispositivo: "Servidor", frecuencia_segundos: 15, snmp_habilitado: false, comunidad_snmp: "public" };

function NodoModal({ onClose, onSaved }) {
  const [f, setF] = useState({ nombre: "", ip: "", url_http: "", ...VACIO });
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  async function guardar() {
    try {
      const body = { ...f, frecuencia_segundos: Number(f.frecuencia_segundos), url_http: f.url_http || null };
      await api("/dispositivos", { method: "POST", body });
      onSaved();
    } catch (x) { setErr(x.message); }
  }
  return (
    <div className="modal"><div>
      <h3>Registrar nuevo nodo</h3>
      <label>Nombre del activo</label><input value={f.nombre} onChange={set("nombre")} placeholder="Switch_Core" />
      <label>Dirección IPv4</label><input value={f.ip} onChange={set("ip")} placeholder="192.168.1.10" />
      <label>Tipo</label>
      <select value={f.tipo_dispositivo} onChange={set("tipo_dispositivo")}>
        {["Switch", "Servidor", "Router", "Firewall"].map((t) => <option key={t}>{t}</option>)}
      </select>
      <label>Frecuencia de escaneo (segundos, mín. 5)</label><input type="number" min="5" value={f.frecuencia_segundos} onChange={set("frecuencia_segundos")} />
      <label>URL HTTP/S a verificar (opcional)</label><input value={f.url_http} onChange={set("url_http")} placeholder="https://intranet.miempresa.cl" />
      <label><input type="checkbox" checked={f.snmp_habilitado} onChange={set("snmp_habilitado")} />Recolectar CPU/RAM/interfaces por SNMP v2c</label>
      {f.snmp_habilitado && <><label>Comunidad SNMP (solo lectura)</label><input value={f.comunidad_snmp} onChange={set("comunidad_snmp")} /></>}
      {err && <div className="err">{err}</div>}
      <div className="row"><button className="btn" onClick={onClose}>Cancelar</button><button className="btn am" onClick={guardar}>Guardar y escanear</button></div>
    </div></div>
  );
}

export default function Dashboard({ can }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(false);
  const [escaneando, setEscaneando] = useState(false);

  const cargar = useCallback(async () => {
    try { setD(await api("/dashboard")); setError(""); } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); const t = setInterval(cargar, 5000); return () => clearInterval(t); }, [cargar]);

  async function escanear() { setEscaneando(true); try { await api("/scan", { method: "POST" }); } finally { setEscaneando(false); cargar(); } }
  async function resolver(id) { await api(`/alertas/${id}/resolver`, { method: "POST" }); cargar(); }
  async function eliminar(n) { if (confirm(`¿Eliminar ${n.nombre} y todo su historial?`)) { await api(`/dispositivos/${n.id}`, { method: "DELETE" }); cargar(); } }

  if (!d) return <div className="panel">{error ? <span className="err">{error}</span> : "Cargando…"}</div>;

  const series = d.nodos.filter((n) => n.historial.length).slice(0, 6).map((n) => ({
    name: n.nombre, data: n.historial.map((h) => ({ x: new Date(h.t).getTime(), y: h.v })),
  }));
  const opciones = {
    chart: { type: "line", height: 260, background: "transparent", toolbar: { show: false }, animations: { enabled: false } },
    theme: { mode: "dark" }, stroke: { curve: "smooth", width: 3 }, markers: { size: 0 },
    colors: ["#f97316", "#0284c7", "#10b981", "#a855f7", "#eab308", "#ec4899"],
    xaxis: { type: "datetime", labels: { datetimeUTC: false, style: { colors: "#64748b" } } },
    yaxis: { min: 0, labels: { formatter: (v) => `${Math.round(v)}ms`, style: { colors: "#64748b" } } },
    grid: { borderColor: "#1e293b", strokeDashArray: 3 },
    legend: { position: "top", horizontalAlign: "right", labels: { colors: "#94a3b8" } },
    noData: { text: "Sin datos aún" },
    annotations: { yaxis: [{ y: 150, borderColor: "#ef4444", strokeDashArray: 4, label: { text: "150 ms (referencia SLA)", style: { color: "#fff", background: "#ef4444" } } }] },
  };
  const r = d.resumen;

  return (
    <>
      <div className="bar">
        <div>
          <div className={"sub " + (error ? "crit" : "ok")}>{error ? "SIN CONEXIÓN CON LA API: " + error : `● EN VIVO · ${r.total} nodos · ${r.activos} activos · ${r.alerta} en alerta · ${r.critico} críticos`}</div>
        </div>
        <div className="tabs">
          {can("GESTIONAR_ALERTAS") && <button className="btn cy" disabled={escaneando} onClick={escanear}>{escaneando ? "⏳ Escaneando…" : "⚡ Escanear red ahora"}</button>}
          {can("CRUD_NODOS") && <button className="btn am" onClick={() => setModal(true)}>+ Nuevo nodo</button>}
        </div>
      </div>

      <div className="grid">
        <div className="c4">
          <div className="panel">
            <h2>KPIs de disponibilidad</h2><p className="d">Uptime últimas 24 h · MTTR últimos 30 días</p>
            <div className="kpis">
              <div className="kpi"><small>Uptime global</small><b className="ok">{d.uptime_global_24h == null ? "—" : `${d.uptime_global_24h.toFixed(2)}%`}</b></div>
              <div className="kpi"><small>MTTR promedio</small><b className="cy">{fmtDur(d.mttr_30d_s)}</b></div>
            </div>
          </div>
          <div className="panel">
            <h2>Incidentes activos <span className="chip crit" style={{ marginLeft: 6 }}>{d.incidentes.length}</span></h2>
            <p className="d">Tabla alerta_log · estado ABIERTA</p>
            <div style={{ maxHeight: 380, overflowY: "auto" }}>
              {d.incidentes.length === 0 && <div className="vacio">✅ Todos los servicios dentro de umbral</div>}
              {d.incidentes.map((i) => (
                <div key={i.id} className={"inc " + (i.criticidad === "Alta" ? "alta" : "")}>
                  <div className="t"><span>{i.nodo} <span className="mut" style={{ fontSize: 10, fontFamily: "monospace" }}>({i.ip})</span></span>
                    {can("GESTIONAR_ALERTAS") && <button className="btn ok" style={{ padding: "3px 8px", fontSize: 10 }} onClick={() => resolver(i.id)}>✓ Resolver</button>}
                  </div>
                  <p>{i.descripcion}</p><small>{i.criticidad} · desde {fmtFecha(i.fecha_hora_creacion)}</small>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="c8">
          <div className="panel">
            <h2>Histórico de latencia ICMP (última hora)</h2><p className="d">Telemetría real almacenada en metrica_historico</p>
            <Chart type="line" height={260} series={series} options={opciones} />
          </div>
          <div className="panel">
            <h2>Inventario tecnológico centralizado</h2><p className="d">Ping ICMP, HTTP/S y sensores SNMP por nodo</p>
            <div className="tbl-wrap"><table>
              <thead><tr><th>ID</th><th>Activo</th><th>IP</th><th>Tipo</th><th>CPU / RAM</th><th>IF↓</th><th>HTTP</th><th>Uptime 24h</th><th>Estado</th><th className="r">Latencia</th>{can("CRUD_NODOS") && <th />}</tr></thead>
              <tbody>
                {d.nodos.map((n) => {
                  const c = COLORES[n.estado] || "mut";
                  return (
                    <tr key={n.id}>
                      <td className="mut">{n.id}</td><td><b>{n.nombre}</b></td><td className="mut">{n.ip}</td><td className="mut">{n.tipo}</td>
                      <td className="cy">{n.cpu != null ? `${n.cpu}%` : "—"} / {n.ram != null ? `${n.ram}%` : "—"}</td>
                      <td>{n.interfaces_down ?? "—"}</td><td>{n.http_status ?? "—"}</td>
                      <td>{n.uptime_24h == null ? "—" : `${n.uptime_24h.toFixed(1)}%`}</td>
                      <td className={c}><b><span className={"dot " + (n.estado === "CRÍTICO" ? "pulse" : "")} />{n.estado}</b></td>
                      <td className={"r " + (n.disponible === false ? "crit" : c)}><b>{n.disponible === false ? "TIMEOUT" : n.latencia_ms != null ? `${n.latencia_ms} ms` : "—"}</b></td>
                      {can("CRUD_NODOS") && <td><button className="btn rd" title="Eliminar" onClick={() => eliminar(n)}>🗑️</button></td>}
                    </tr>
                  );
                })}
              </tbody>
            </table></div>
          </div>
        </div>
      </div>
      {modal && <NodoModal onClose={() => setModal(false)} onSaved={() => { setModal(false); cargar(); }} />}
    </>
  );
}
