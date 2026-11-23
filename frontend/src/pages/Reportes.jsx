import { useEffect, useState } from "react";
import { api, descargar, fmtDur, fmtFecha } from "../api";

export default function Reportes() {
  const [dias, setDias] = useState(7);
  const [sla, setSla] = useState(null);
  const [inc, setInc] = useState([]);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState("");

  useEffect(() => {
    api(`/reportes/sla?dias=${dias}`).then(setSla).catch((e) => setError(e.message));
    api(`/reportes/incidentes?dias=${dias}`).then(setInc).catch(() => {});
  }, [dias]);

  async function bajar(tipo) {
    setBajando(tipo); setError("");
    try {
      if (tipo === "xlsx") await descargar(`/reportes/sla.xlsx?dias=${dias}&tz_offset_min=${new Date().getTimezoneOffset()}`, `informe_sla_${dias}d.xlsx`);
      else await descargar(`/reportes/sla.csv?dias=${dias}`, `sla_${dias}d.csv`);
    } catch (e) { setError(e.message); }
    setBajando("");
  }

  return (
    <>
      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <div><h2>Informe de disponibilidad y cumplimiento de SLA</h2>
            <p className="d">Objetivo SLA: {sla?.sla_objetivo_pct}% · Uptime global: <b className="ok">{sla?.uptime_global_pct ?? "—"}%</b> · MTTR: <b className="cy">{fmtDur(sla?.mttr_global_s)}</b></p></div>
          <div className="tabs no-print">
            <select style={{ width: 140 }} value={dias} onChange={(e) => setDias(Number(e.target.value))}>
              {[1, 7, 30, 90].map((d) => <option key={d} value={d}>Últimos {d} día(s)</option>)}
            </select>
            <button className="btn cy" disabled={!!bajando} onClick={() => bajar("xlsx")}>{bajando === "xlsx" ? "Generando…" : "📊 Descargar informe Excel"}</button>
            <button className="btn" onClick={() => window.print()}>🖨 Imprimir / guardar PDF</button>
            <button className="btn" disabled={!!bajando} onClick={() => bajar("csv")} title="Datos en bruto, compatibles con Excel en español">⬇ CSV</button>
          </div>
        </div>
        {error && <div className="err">{error}</div>}
        <div className="tbl-wrap"><table>
          <thead><tr><th>Nodo</th><th>IP</th><th>Muestras</th><th>Uptime</th><th>Downtime est.</th><th>Lat. prom.</th><th>Lat. máx.</th><th>Incid.</th><th>MTTR</th><th>SLA</th></tr></thead>
          <tbody>
            {sla && sla.nodos.length === 0 && <tr><td colSpan={10} className="mut">No hay nodos registrados.</td></tr>}
            {sla?.nodos.map((n) => (
              <tr key={n.dispositivo_id}>
                <td><b>{n.nodo}</b></td><td className="mut">{n.ip}</td><td>{n.muestras}</td>
                <td>{n.uptime_pct ?? "—"}%</td><td>{fmtDur(n.downtime_estimado_s)}</td>
                <td>{n.latencia_prom_ms ?? "—"} ms</td><td>{n.latencia_max_ms ?? "—"} ms</td>
                <td>{n.incidentes}</td><td>{fmtDur(n.mttr_s)}</td>
                <td className={n.cumple_sla == null ? "mut" : n.cumple_sla ? "ok" : "crit"}><b>{n.cumple_sla == null ? "s/d" : n.cumple_sla ? "CUMPLE" : "NO CUMPLE"}</b></td>
              </tr>))}
          </tbody>
        </table></div>
      </div>
      <div className="panel">
        <h2>Registro histórico de incidencias</h2><p className="d">Trazabilidad centralizada de eventos (tabla alerta_log)</p>
        <div className="tbl-wrap"><table>
          <thead><tr><th>#</th><th>Nodo</th><th>Criticidad</th><th>Descripción</th><th>Inicio</th><th>Fin</th><th>Duración</th><th>Estado</th></tr></thead>
          <tbody>
            {inc.length === 0 && <tr><td colSpan={8} className="mut">Sin incidentes en el período.</td></tr>}
            {inc.map((i) => (
              <tr key={i.id}><td>{i.id}</td><td><b>{i.nodo}</b></td><td className={i.criticidad === "Crítica" ? "crit" : "warn"}>{i.criticidad}</td>
                <td style={{ fontFamily: "sans-serif" }}>{i.descripcion}</td><td>{fmtFecha(i.fecha_hora_creacion)}</td><td>{fmtFecha(i.fecha_hora_resolucion)}</td>
                <td>{fmtDur(i.duracion_s)}</td><td className={i.estado_alerta === "ABIERTA" ? "crit" : "ok"}>{i.estado_alerta}</td></tr>))}
          </tbody>
        </table></div>
      </div>
    </>
  );
}
