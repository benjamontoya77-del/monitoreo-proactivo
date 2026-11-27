import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import auditar, requiere
from ..models import AuditoriaAcceso, Rol, Usuario
from ..schemas import UsuarioActualizar, UsuarioCrear, UsuarioOut
from ..security import hash_password
from ..services.notifier import enviar_correo_usuario
from .auth import usuario_out

router = APIRouter(tags=["usuarios"])


@router.get("/roles")
async def roles(db: AsyncSession = Depends(get_db), _=Depends(requiere("GESTIONAR_USUARIOS"))):
    return [{"id": r.id, "nombre_rol": r.nombre_rol, "permisos": list(r.permisos)}
            for r in (await db.scalars(select(Rol))).all()]


@router.get("/usuarios", response_model=list[UsuarioOut])
async def listar(db: AsyncSession = Depends(get_db), _=Depends(requiere("GESTIONAR_USUARIOS"))):
    return [usuario_out(u) for u in (await db.scalars(select(Usuario).order_by(Usuario.id))).all()]


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
async def crear(datos: UsuarioCrear, request: Request, db: AsyncSession = Depends(get_db),
                admin: Usuario = Depends(requiere("GESTIONAR_USUARIOS"))):
    username = datos.username.strip()
    email = datos.email.strip().lower()

    rol = await db.get(Rol, datos.rol_id)
    if not rol:
        raise HTTPException(404, "Rol no encontrado")

    if await db.scalar(select(Usuario).where(func.lower(Usuario.username) == username.lower())):
        raise HTTPException(409, f"No se puede registrar: el usuario '{username}' ya está registrado.")

    if await db.scalar(select(Usuario).where(func.lower(Usuario.email) == email)):
        raise HTTPException(409, f"No se puede registrar: el correo '{email}' ya está registrado.")

    u = Usuario(username=username, email=email, rol_id=datos.rol_id,
                password_hash=hash_password(datos.password))
    db.add(u)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No se puede registrar: el usuario o correo ya existe.")
    await db.refresh(u)
    await auditar(db, admin, "USUARIO_CREADO", f"{u.username} ({u.email})", request)

    if u.email:
        fecha_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        asunto = f"Cuenta registrada correctamente — {u.username} (Monitor Proactivo TI)"
        cuerpo = (
            f"Hola {u.username},\n\n"
            f"Tu correo electrónico ha sido registrado correctamente en la plataforma NOC — Monitoreo Proactivo.\n\n"
            f"• Usuario asignado: {u.username}\n"
            f"• Correo registrado: {u.email}\n"
            f"• Rol asignado: {rol.nombre_rol}\n"
            f"• Registrado por: {admin.username}\n"
            f"• Fecha de registro: {fecha_utc}\n\n"
            f"Ya puedes ingresar al Dashboard con las credenciales asignadas por el Administrador TI."
        )
        asyncio.create_task(
            enviar_correo_usuario(
                destinatario=u.email,
                asunto=asunto,
                texto=cuerpo,
                silencioso=True,
            )
        )

    return usuario_out(u)


@router.patch("/usuarios/{uid}", response_model=UsuarioOut)
async def actualizar(uid: int, datos: UsuarioActualizar, request: Request, db: AsyncSession = Depends(get_db),
                     admin: Usuario = Depends(requiere("GESTIONAR_USUARIOS"))):
    u = await db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if uid == admin.id and datos.activo is False:
        raise HTTPException(400, "No puedes desactivar tu propia cuenta")
    if u.username.lower() == "admin" and datos.activo is False:
        raise HTTPException(400, "No se puede desactivar la cuenta principal admin")
    if datos.activo is not None:
        u.activo = datos.activo
    if datos.rol_id is not None:
        if not await db.get(Rol, datos.rol_id):
            raise HTTPException(404, "Rol no encontrado")
        u.rol_id = datos.rol_id
    if datos.password:
        u.password_hash = hash_password(datos.password)
    await db.commit()
    await db.refresh(u)
    await auditar(db, admin, "USUARIO_EDITADO", u.username, request)
    return usuario_out(u)


@router.delete("/usuarios/{uid}", status_code=204)
async def eliminar(uid: int, request: Request, db: AsyncSession = Depends(get_db),
                   admin: Usuario = Depends(requiere("GESTIONAR_USUARIOS"))):
    u = await db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if uid == admin.id:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta activa")
    if u.username.lower() == "admin":
        raise HTTPException(400, "No se puede eliminar la cuenta principal admin")
    eliminado = f"{u.username} ({u.email})"
    await db.delete(u)
    await db.commit()
    await auditar(db, admin, "USUARIO_ELIMINADO", eliminado, request)


@router.get("/auditoria")
async def auditoria(limit: int = 200, db: AsyncSession = Depends(get_db), _=Depends(requiere("GESTIONAR_USUARIOS"))):
    q = select(AuditoriaAcceso).order_by(AuditoriaAcceso.id.desc()).limit(min(limit, 1000))
    return [{"id": a.id, "username": a.username, "accion": a.accion, "detalle": a.detalle,
             "ip_origen": a.ip_origen, "fecha": a.fecha.isoformat() + "Z"} for a in (await db.scalars(q)).all()]