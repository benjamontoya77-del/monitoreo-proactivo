from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import AuditoriaAcceso, Usuario
from .security import decodificar_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def usuario_actual(token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)) -> Usuario:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas o sesión expirada",
                          headers={"WWW-Authenticate": "Bearer"})
    username = decodificar_token(token)
    if not username:
        raise error
    user = await db.scalar(select(Usuario).where(Usuario.username == username))
    if not user or not user.activo:
        raise error
    return user


def requiere(*permisos: str):
    """Dependencia RBAC: exige que el rol del usuario contenga TODOS los permisos indicados."""
    async def _dep(user: Usuario = Depends(usuario_actual)) -> Usuario:
        if not set(permisos) <= set(user.rol.permisos):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Permiso requerido: {', '.join(permisos)}")
        return user
    return _dep


async def auditar(db: AsyncSession, user: Usuario | None, accion: str, detalle: str = "",
                  request: Request | None = None, username: str | None = None) -> None:
    db.add(AuditoriaAcceso(
        usuario_id=user.id if user else None,
        username=user.username if user else username,
        accion=accion, detalle=detalle[:500],
        ip_origen=request.client.host if request and request.client else None,
    ))
    await db.commit()
