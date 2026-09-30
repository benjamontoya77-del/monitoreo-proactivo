from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import auditar, requiere
from ..models import AlertaLog, Dispositivo, ReglaUmbral, Usuario, ahora
from ..schemas import AlertaOut
from ..services import monitor, notifier
from ..services.sla import alerta_a_dict

router = APIRouter(prefix="/alertas", tags=["alertas"])


@router.get("", response_model=list[AlertaOut])
async def listar(estado: Literal["ABIERTA", "RESUELTA"] | None = None, limit: int = Query(100, ge=1, le=1000),
                 db: AsyncSession = Depends(get_db), _=Depends(requiere("VER_DASHBOARD"))):
    q = (select(AlertaLog, Dispositivo.nombre, Dispositivo.ip, ReglaUmbral.parametro, ReglaUmbral.criticidad)
         .join(Dispositivo, Dispositivo.id == AlertaLog.dispositivo_id)
         .join(ReglaUmbral, ReglaUmbral.id == AlertaLog.regla_id)
         .order_by(AlertaLog.id.desc()).limit(limit))
    if estado:
        q = q.where(AlertaLog.estado_alerta == estado)
    return [alerta_a_dict(*row) for row in (await db.execute(q)).all()]


@router.post("/{alerta_id}/resolver", response_model=AlertaOut)
async def resolver(alerta_id: int, request: Request, db: AsyncSession = Depends(get_db),
                   user: Usuario = Depends(requiere("GESTIONAR_ALERTAS"))):
    """Cierre manual (reconocimiento). Si la condición persiste, el motor volverá a abrirla en el próximo ciclo."""
    fila = (await db.execute(
        select(AlertaLog, Dispositivo, ReglaUmbral).join(Dispositivo, Dispositivo.id == AlertaLog.dispositivo_id)
        .join(ReglaUmbral, ReglaUmbral.id == AlertaLog.regla_id).where(AlertaLog.id == alerta_id))).first()
    if not fila:
        raise HTTPException(404, "Alerta no encontrada")
    alerta, disp, regla = fila
    if alerta.estado_alerta == "RESUELTA":
        raise HTTPException(409, "La alerta ya estaba resuelta")
    alerta.estado_alerta, alerta.fecha_hora_resolucion = "RESUELTA", ahora()
    await db.flush()
    await monitor.recalcular_estado(db, disp)
    await db.commit()
    await auditar(db, user, "ALERTA_RESUELTA", f"id={alerta_id} {disp.nombre}", request)
    dur = int((alerta.fecha_hora_resolucion - alerta.fecha_hora_creacion).total_seconds())
    await notifier.notificar(monitor.formatear(False, regla.criticidad, alerta.descripcion, dur) +
                             f"\n(cierre manual por {user.username})", asunto="Alerta resuelta")
    return alerta_a_dict(alerta, disp.nombre, disp.ip, regla.parametro, regla.criticidad)
