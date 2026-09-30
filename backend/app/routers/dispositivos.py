from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import auditar, requiere
from ..models import AlertaLog, Dispositivo, MetricaHistorico, ReglaUmbral, Usuario, ahora
from ..schemas import DispositivoActualizar, DispositivoCrear, DispositivoOut, MetricaOut
from ..services.planificador import planificador

router = APIRouter(prefix="/dispositivos", tags=["dispositivos"])


@router.get("", response_model=list[DispositivoOut])
async def listar(db: AsyncSession = Depends(get_db), _=Depends(requiere("VER_DASHBOARD"))):
    return (await db.scalars(select(Dispositivo).order_by(Dispositivo.id))).all()


@router.post("", response_model=DispositivoOut, status_code=201)
async def crear(datos: DispositivoCrear, request: Request, bg: BackgroundTasks,
                db: AsyncSession = Depends(get_db), user: Usuario = Depends(requiere("CRUD_NODOS"))):
    disp = Dispositivo(**datos.model_dump())
    db.add(disp)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Ya existe un dispositivo con esa IP")
    # Regla base: toda caída de un nodo es una alerta crítica.
    db.add(ReglaUmbral(dispositivo_id=disp.id, parametro="disponibilidad", valor_umbral=1, criticidad="Crítica"))
    await db.commit()
    await auditar(db, user, "NODO_CREADO", f"{disp.nombre} ({disp.ip})", request)
    bg.add_task(planificador.escanear, disp.id)  # primer sondeo inmediato
    return disp


@router.put("/{disp_id}", response_model=DispositivoOut)
async def actualizar(disp_id: int, datos: DispositivoActualizar, request: Request,
                     db: AsyncSession = Depends(get_db), user: Usuario = Depends(requiere("CRUD_NODOS"))):
    disp = await db.get(Dispositivo, disp_id)
    if not disp:
        raise HTTPException(404, "Dispositivo no encontrado")
    for k, v in datos.model_dump(exclude_unset=True).items():
        setattr(disp, k, v)
    await db.commit()
    await auditar(db, user, "NODO_EDITADO", f"id={disp_id}", request)
    return disp


@router.delete("/{disp_id}", status_code=204)
async def eliminar(disp_id: int, request: Request, db: AsyncSession = Depends(get_db),
                   user: Usuario = Depends(requiere("CRUD_NODOS"))):
    disp = await db.get(Dispositivo, disp_id)
    if not disp:
        raise HTTPException(404, "Dispositivo no encontrado")
    nombre = f"{disp.nombre} ({disp.ip})"
    # Borrado explícito (en PostgreSQL además existe ON DELETE CASCADE).
    for tabla in (AlertaLog, MetricaHistorico, ReglaUmbral):
        await db.execute(delete(tabla).where(tabla.dispositivo_id == disp_id))
    await db.delete(disp)
    await db.commit()
    await auditar(db, user, "NODO_ELIMINADO", nombre, request)


@router.get("/{disp_id}/metricas", response_model=list[MetricaOut])
async def metricas(disp_id: int, minutos: int = Query(60, ge=1, le=10080), db: AsyncSession = Depends(get_db),
                   _=Depends(requiere("VER_DASHBOARD"))):
    desde = ahora() - timedelta(minutes=minutos)
    q = (select(MetricaHistorico).where(MetricaHistorico.dispositivo_id == disp_id,
                                        MetricaHistorico.timestamp >= desde).order_by(MetricaHistorico.id))
    return (await db.scalars(q)).all()
