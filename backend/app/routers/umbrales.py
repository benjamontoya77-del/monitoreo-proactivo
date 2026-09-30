from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import auditar, requiere
from ..models import Dispositivo, ReglaUmbral, Usuario
from ..schemas import UmbralActualizar, UmbralCrear, UmbralOut

router = APIRouter(prefix="/umbrales", tags=["umbrales"])


@router.get("", response_model=list[UmbralOut])
async def listar(dispositivo_id: int | None = None, db: AsyncSession = Depends(get_db),
                 _=Depends(requiere("VER_DASHBOARD"))):
    q = select(ReglaUmbral).order_by(ReglaUmbral.id)
    if dispositivo_id:
        q = q.where(ReglaUmbral.dispositivo_id == dispositivo_id)
    return (await db.scalars(q)).all()


@router.post("", response_model=UmbralOut, status_code=201)
async def crear(datos: UmbralCrear, request: Request, db: AsyncSession = Depends(get_db),
                user: Usuario = Depends(requiere("CONFIG_UMBRALES"))):
    if not await db.get(Dispositivo, datos.dispositivo_id):
        raise HTTPException(404, "Dispositivo no encontrado")
    regla = ReglaUmbral(**datos.model_dump())
    db.add(regla)
    await db.commit()
    await auditar(db, user, "UMBRAL_CREADO", f"disp={regla.dispositivo_id} {regla.parametro}>{regla.valor_umbral}", request)
    return regla


@router.put("/{regla_id}", response_model=UmbralOut)
async def actualizar(regla_id: int, datos: UmbralActualizar, request: Request, db: AsyncSession = Depends(get_db),
                     user: Usuario = Depends(requiere("CONFIG_UMBRALES"))):
    regla = await db.get(ReglaUmbral, regla_id)
    if not regla:
        raise HTTPException(404, "Regla no encontrada")
    for k, v in datos.model_dump(exclude_unset=True).items():
        setattr(regla, k, v)
    await db.commit()
    await auditar(db, user, "UMBRAL_EDITADO", f"id={regla_id}", request)
    return regla


@router.delete("/{regla_id}", status_code=204)
async def eliminar(regla_id: int, request: Request, db: AsyncSession = Depends(get_db),
                   user: Usuario = Depends(requiere("CONFIG_UMBRALES"))):
    regla = await db.get(ReglaUmbral, regla_id)
    if not regla:
        raise HTTPException(404, "Regla no encontrada")
    await db.delete(regla)
    await db.commit()
    await auditar(db, user, "UMBRAL_ELIMINADO", f"id={regla_id}", request)
