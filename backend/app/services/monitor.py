"""Persistencia de resultados + evaluación de reglas + notificaciones (RF2, RF3)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AlertaLog, Dispositivo, MetricaHistorico, ReglaUmbral, ahora
from . import notifier
from .reglas import calcular_estado, decidir
from .scanner import Resultado, escanear_dispositivo

# Referencia indirecta para poder sustituir el escáner en pruebas.
escanear = escanear_dispositivo


def formatear(abierta: bool, criticidad: str, descripcion: str, duracion_s: int | None = None) -> str:
    if abierta:
        icono = "🔴" if criticidad == "Crítica" else "🟠"
        return f"{icono} ALERTA {criticidad.upper()}\n{descripcion}"
    extra = f" (duración: {duracion_s}s)" if duracion_s is not None else ""
    return f"✅ RESUELTA\n{descripcion}{extra}"


async def _criticidades_abiertas(db: AsyncSession, disp_id: int) -> list[str]:
    q = (select(ReglaUmbral.criticidad).join(AlertaLog, AlertaLog.regla_id == ReglaUmbral.id)
         .where(AlertaLog.dispositivo_id == disp_id, AlertaLog.estado_alerta == "ABIERTA"))
    return list((await db.scalars(q)).all())


async def recalcular_estado(db: AsyncSession, disp: Dispositivo, disponible: bool | None = None) -> None:
    if disponible is None:
        ultima = await db.scalar(select(MetricaHistorico.disponible)
                                 .where(MetricaHistorico.dispositivo_id == disp.id)
                                 .order_by(MetricaHistorico.id.desc()).limit(1))
        disponible = True if ultima is None else ultima
    disp.estado_actual = calcular_estado(disponible, await _criticidades_abiertas(db, disp.id))


async def procesar_resultado(db: AsyncSession, disp: Dispositivo, r: Resultado) -> list[str]:
    db.add(MetricaHistorico(dispositivo_id=disp.id, latencia_ms=r.latencia_ms, uso_cpu_pct=r.cpu,
                            uso_ram_pct=r.ram, interfaces_down=r.interfaces_down,
                            http_status=r.http_status, disponible=r.disponible))
    reglas = (await db.scalars(select(ReglaUmbral).where(ReglaUmbral.dispositivo_id == disp.id))).all()
    abiertas = {a.regla_id: a for a in (await db.scalars(
        select(AlertaLog).where(AlertaLog.dispositivo_id == disp.id, AlertaLog.estado_alerta == "ABIERTA"))).all()}
    por_id = {rg.id: rg for rg in reglas}

    dec = decidir(reglas, set(abiertas), r, disp.nombre, disp.ip)
    mensajes: list[str] = []
    for regla, desc in dec.abrir:
        db.add(AlertaLog(dispositivo_id=disp.id, regla_id=regla.id, descripcion=desc[:255]))
        mensajes.append(formatear(True, regla.criticidad, desc))
    for rid in dec.resolver:
        a = abiertas[rid]
        a.estado_alerta, a.fecha_hora_resolucion = "RESUELTA", ahora()
        dur = int((a.fecha_hora_resolucion - a.fecha_hora_creacion).total_seconds())
        mensajes.append(formatear(False, por_id[rid].criticidad, a.descripcion, dur))

    await db.flush()
    await recalcular_estado(db, disp, r.disponible)
    await db.commit()
    return mensajes


async def escanear_y_procesar(db: AsyncSession, disp: Dispositivo) -> None:
    resultado = await escanear(disp)
    mensajes = await procesar_resultado(db, disp, resultado)
    for m in mensajes:
        await notifier.notificar(m, asunto=m.splitlines()[0])
