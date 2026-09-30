from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import auditar, usuario_actual
from ..models import Usuario
from ..schemas import TokenOut, UsuarioOut
from ..security import crear_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def usuario_out(u: Usuario) -> UsuarioOut:
    return UsuarioOut(id=u.id, username=u.username, email=u.email, activo=u.activo,
                      rol=u.rol.nombre_rol, permisos=list(u.rol.permisos))


@router.post("/login", response_model=TokenOut)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    u = await db.scalar(select(Usuario).where(Usuario.username == form.username))
    if not u or not u.activo or not verify_password(form.password, u.password_hash):
        await auditar(db, None, "LOGIN_FALLIDO", f"usuario={form.username}", request, username=form.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
    await auditar(db, u, "LOGIN", "", request)
    return TokenOut(access_token=crear_token(u.username), usuario=usuario_out(u))


@router.get("/me", response_model=UsuarioOut)
async def me(u: Usuario = Depends(usuario_actual)):
    return usuario_out(u)
