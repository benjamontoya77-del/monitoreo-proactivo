"""Reportabilidad: Uptime, MTTR y cumplimiento de SLA (RF de Módulo de Reportabilidad)."""
from datetime import timedelta

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import AlertaLog, Dispositivo, MetricaHistorico, ReglaUmbral, ahora


def porcentaje_uptime(disponibles: int, total: int) -> float | None:
    return None if not total else round(disponibles / total * 100, 3)


def mttr_segundos(duraciones: list[float]) -> int | None:
    return round(sum(duraciones) / len(duraciones)) if duraciones else None


async def uptime_por_dispositivo(db: AsyncSession, desde) -> dict[int, tuple[int, int, float | None, int | None]]:
    """{disp_id: (muestras, disponibles, lat_prom, lat_max)}"""
    q = (select(MetricaHistorico.dispositivo_id, func.count(MetricaHistorico.id),
                func.sum(case((MetricaHistorico.disponible.is_(True), 1), else_=0).cast(Integer)),
                func.avg(MetricaHistorico.latencia_ms), func.max(MetricaHistorico.latencia_ms))
         .where(MetricaHistorico.timestamp >= desde).group_by(MetricaHistorico.dispositivo_id))
    return {r[0]: (r[1], int(r[2] or 0), r[3], r[4]) for r in (await db.execute(q)).all()}


async def duraciones_resueltas(db: AsyncSession, desde, disp_id: int | None = None) -> list[float]:
    q = select(AlertaLog.fecha_hora_creacion, AlertaLog.fecha_hora_resolucion).where(
        AlertaLog.estado_alerta == "RESUELTA", AlertaLog.fecha_hora_creacion >= desde)
    if disp_id:
        q = q.where(AlertaLog.dispositivo_id == disp_id)
    return [(fin - ini).total_seconds() for ini, fin in (await db.execute(q)).all() if fin]


async def reporte_sla(db: AsyncSession, dias: int) -> dict:
    desde = ahora() - timedelta(days=dias)
    uptimes = await uptime_por_dispositivo(db, desde)
    filas = []
    for d in (await db.scalars(select(Dispositivo).order_by(Dispositivo.nombre))).all():
        muestras, ok, lat_prom, lat_max = uptimes.get(d.id, (0, 0, None, None))
        up = porcentaje_uptime(ok, muestras)
        n_inc = await db.scalar(select(func.count(AlertaLog.id)).where(
            AlertaLog.dispositivo_id == d.id, AlertaLog.fecha_hora_creacion >= desde)) or 0
        filas.append({
            "dispositivo_id": d.id, "nodo": d.nombre, "ip": d.ip, "tipo": d.tipo_dispositivo,
            "muestras": muestras, "uptime_pct": up,
            "downtime_estimado_s": None if up is None else round((100 - up) / 100 * dias * 86400),
            "latencia_prom_ms": None if lat_prom is None else round(float(lat_prom), 1),
            "latencia_max_ms": lat_max, "incidentes": n_inc,
            "mttr_s": mttr_segundos(await duraciones_resueltas(db, desde, d.id)),
            "cumple_sla": None if up is None else up >= settings.sla_objetivo_pct,
        })
    tot = sum(m for m, *_ in uptimes.values())
    ok_tot = sum(o for _, o, *_ in uptimes.values())
    return {"dias": dias, "sla_objetivo_pct": settings.sla_objetivo_pct,
            "uptime_global_pct": porcentaje_uptime(ok_tot, tot),
            "mttr_global_s": mttr_segundos(await duraciones_resueltas(db, desde)), "nodos": filas}


async def historial_incidentes(db: AsyncSession, dias: int) -> list[dict]:
    desde = ahora() - timedelta(days=dias)
    q = (select(AlertaLog, Dispositivo.nombre, Dispositivo.ip, ReglaUmbral.parametro, ReglaUmbral.criticidad)
         .join(Dispositivo, Dispositivo.id == AlertaLog.dispositivo_id)
         .join(ReglaUmbral, ReglaUmbral.id == AlertaLog.regla_id)
         .where(AlertaLog.fecha_hora_creacion >= desde).order_by(AlertaLog.id.desc()))
    return [alerta_a_dict(a, n, ip, p, c) for a, n, ip, p, c in (await db.execute(q)).all()]


def alerta_a_dict(a: AlertaLog, nodo: str, ip: str, parametro: str, criticidad: str) -> dict:
    fin = a.fecha_hora_resolucion
    return {"id": a.id, "dispositivo_id": a.dispositivo_id, "nodo": nodo, "ip": ip, "parametro": parametro,
            "criticidad": criticidad, "descripcion": a.descripcion, "estado_alerta": a.estado_alerta,
            "fecha_hora_creacion": a.fecha_hora_creacion, "fecha_hora_resolucion": fin,
            "duracion_s": int((fin - a.fecha_hora_creacion).total_seconds()) if fin else None}
