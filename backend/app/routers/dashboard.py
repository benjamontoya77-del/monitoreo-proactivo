from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import requiere
from ..models import AlertaLog, Dispositivo, MetricaHistorico, ReglaUmbral, ahora
from ..services import sla
from ..services.planificador import planificador

router = APIRouter(tags=["dashboard"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db), _=Depends(requiere("VER_DASHBOARD"))):
    ahora_ = ahora()
    dispositivos = (await db.scalars(select(Dispositivo).order_by(Dispositivo.id))).all()

    # Última lectura de cada nodo
    ult_ids = select(func.max(MetricaHistorico.id)).group_by(MetricaHistorico.dispositivo_id)
    ultimas = {m.dispositivo_id: m for m in (await db.scalars(
        select(MetricaHistorico).where(MetricaHistorico.id.in_(ult_ids)))).all()}

    # Historial reciente (última hora) para el gráfico de latencia
    hist = defaultdict(list)
    q = select(MetricaHistorico).where(MetricaHistorico.timestamp >= ahora_ - timedelta(hours=1)).order_by(MetricaHistorico.id)
    for m in (await db.scalars(q)).all():
        hist[m.dispositivo_id].append({"t": m.timestamp.isoformat() + "Z", "v": m.latencia_ms})

    up24 = await sla.uptime_por_dispositivo(db, ahora_ - timedelta(hours=24))
    nodos = []
    for d in dispositivos:
        m = ultimas.get(d.id)
        muestras, ok, *_ = up24.get(d.id, (0, 0, None, None))
        nodos.append({
            "id": d.id, "nombre": d.nombre, "ip": d.ip, "tipo": d.tipo_dispositivo, "estado": d.estado_actual,
            "frecuencia_segundos": d.frecuencia_segundos, "snmp": d.snmp_habilitado, "url_http": d.url_http,
            "disponible": m.disponible if m else None, "latencia_ms": m.latencia_ms if m else None,
            "cpu": m.uso_cpu_pct if m else None, "ram": m.uso_ram_pct if m else None,
            "interfaces_down": m.interfaces_down if m else None, "http_status": m.http_status if m else None,
            "ultima_lectura": m.timestamp.isoformat() + "Z" if m else None,
            "uptime_24h": sla.porcentaje_uptime(ok, muestras), "historial": hist.get(d.id, [])[-40:],
        })

    q = (select(AlertaLog, Dispositivo.nombre, Dispositivo.ip, ReglaUmbral.parametro, ReglaUmbral.criticidad)
         .join(Dispositivo, Dispositivo.id == AlertaLog.dispositivo_id)
         .join(ReglaUmbral, ReglaUmbral.id == AlertaLog.regla_id)
         .where(AlertaLog.estado_alerta == "ABIERTA").order_by(AlertaLog.id.desc()))
    incidentes = [sla.alerta_a_dict(*r) for r in (await db.execute(q)).all()]

    tot = sum(v[0] for v in up24.values())
    ok_tot = sum(v[1] for v in up24.values())
    mttr = sla.mttr_segundos(await sla.duraciones_resueltas(db, ahora_ - timedelta(days=30)))
    return {
        "uptime_global_24h": sla.porcentaje_uptime(ok_tot, tot), "mttr_30d_s": mttr,
        "resumen": {"total": len(nodos), "activos": sum(n["estado"] == "ACTIVO" for n in nodos),
                    "alerta": sum(n["estado"] == "ALERTA" for n in nodos),
                    "critico": sum(n["estado"] == "CRÍTICO" for n in nodos)},
        "nodos": nodos, "incidentes": incidentes, "generado": ahora_.isoformat() + "Z",
    }


@router.post("/scan", status_code=202)
async def escanear_ahora(_=Depends(requiere("GESTIONAR_ALERTAS"))):
    """Fuerza un ciclo de escaneo inmediato de toda la red (botón del dashboard)."""
    await planificador.escanear_todos()
    return {"status": "completado"}
