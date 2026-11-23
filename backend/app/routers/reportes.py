import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import requiere
from ..services import informes, sla

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/sla")
async def informe_sla(dias: int = Query(7, ge=1, le=365), db: AsyncSession = Depends(get_db),
                      _=Depends(requiere("VER_REPORTES"))):
    return await sla.reporte_sla(db, dias)


@router.get("/sla.xlsx")
async def informe_sla_xlsx(dias: int = Query(7, ge=1, le=365),
                           tz_offset_min: int = Query(0, ge=-840, le=840),
                           db: AsyncSession = Depends(get_db), _=Depends(requiere("VER_REPORTES"))):
    """Informe en Excel con formato (hojas: Resumen SLA, Incidentes, Notas)."""
    contenido = informes.construir_xlsx(await sla.reporte_sla(db, dias), await sla.historial_incidentes(db, dias),
                                        tz_offset_min)
    return Response(contenido,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="informe_sla_{dias}d.xlsx"'})


def _num(v):
    """Número con coma decimal (Excel en configuración regional es-CL/es-ES)."""
    return "" if v is None else str(v).replace(".", ",")


@router.get("/sla.csv")
async def informe_sla_csv(dias: int = Query(7, ge=1, le=365), db: AsyncSession = Depends(get_db),
                          _=Depends(requiere("VER_REPORTES"))):
    """CSV compatible con Excel en español: UTF-8 con BOM (tildes correctas), separador ';' y decimales con coma."""
    data = await sla.reporte_sla(db, dias)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["nodo", "ip", "tipo", "muestras", "uptime_pct", "downtime_estimado_s", "latencia_prom_ms",
                "latencia_max_ms", "incidentes", "mttr_s", "cumple_sla"])
    for n in data["nodos"]:
        w.writerow([n["nodo"], n["ip"], n["tipo"], n["muestras"], _num(n["uptime_pct"]), n["downtime_estimado_s"],
                    _num(n["latencia_prom_ms"]), n["latencia_max_ms"], n["incidentes"], n["mttr_s"],
                    {None: "s/d", True: "SI", False: "NO"}[n["cumple_sla"]]])
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="sla_{dias}d.csv"'})


@router.get("/incidentes")
async def informe_incidentes(dias: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db),
                             _=Depends(requiere("VER_REPORTES"))):
    return await sla.historial_incidentes(db, dias)
