import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import requiere
from ..services import sla

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/sla")
async def informe_sla(dias: int = Query(7, ge=1, le=365), db: AsyncSession = Depends(get_db),
                      _=Depends(requiere("VER_REPORTES"))):
    return await sla.reporte_sla(db, dias)


@router.get("/sla.csv")
async def informe_sla_csv(dias: int = Query(7, ge=1, le=365), db: AsyncSession = Depends(get_db),
                          _=Depends(requiere("VER_REPORTES"))):
    data = await sla.reporte_sla(db, dias)
    buf = io.StringIO()
    w = csv.writer(buf)
    campos = ["nodo", "ip", "tipo", "muestras", "uptime_pct", "downtime_estimado_s", "latencia_prom_ms",
              "latencia_max_ms", "incidentes", "mttr_s", "cumple_sla"]
    w.writerow(campos)
    for n in data["nodos"]:
        w.writerow([n[c] for c in campos])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="sla_{dias}d.csv"'})


@router.get("/incidentes")
async def informe_incidentes(dias: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db),
                             _=Depends(requiere("VER_REPORTES"))):
    return await sla.historial_incidentes(db, dias)
