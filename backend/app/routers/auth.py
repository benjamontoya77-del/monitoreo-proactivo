import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import auditar, usuario_actual
from ..models import Usuario
from ..schemas import TokenOut, UsuarioOut
from ..security import crear_token, verify_password
from ..services.notifier import enviar_correo_usuario

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


def usuario_out(u: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=u.id,
        username=u.username,
        email=u.email,
        activo=u.activo,
        rol=u.rol.nombre_rol,
        permisos=list(u.rol.permisos),
    )


@router.post("/login", response_model=TokenOut)
@limiter.limit("5/minute")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    u = await db.scalar(select(Usuario).where(Usuario.username == form.username))
    if not u or not u.activo or not verify_password(form.password, u.password_hash):
        await auditar(db, None, "LOGIN_FALLIDO", f"usuario={form.username}", request, username=form.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")

    await auditar(db, u, "LOGIN", "", request)

    if u.email:
        ip_origen = request.client.host if request.client else "desconocida"
        fecha_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        asunto = f"Inicio de sesión detectado — {u.username} (Monitor Proactivo TI)"
        cuerpo = (
            f"Hola {u.username},\n\n"
            f"Se ha registrado un inicio de sesión en la plataforma NOC — Monitoreo Proactivo.\n\n"
            f"• Usuario: {u.username}\n"
            f"• Rol asignado: {u.rol.nombre_rol}\n"
            f"• Fecha y hora: {fecha_utc}\n"
            f"• Dirección IP de origen: {ip_origen}\n\n"
            f"Si no reconoces este acceso, contacta al Administrador TI."
        )
        asyncio.create_task(
            enviar_correo_usuario(
                destinatario=u.email,
                asunto=asunto,
                texto=cuerpo,
                silencioso=True,
            )
        )

    return TokenOut(access_token=crear_token(u.username), usuario=usuario_out(u))


@router.get("/me", response_model=UsuarioOut)
async def me(u: Usuario = Depends(usuario_actual)):
    return usuario_out(u)