import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Rol, Usuario
from .routers import alertas, auth, dashboard, dispositivos, reportes, umbrales, usuarios
from .security import hash_password
from .services.planificador import planificador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

PERMISOS_ADMIN = ["CRUD_NODOS", "CONFIG_UMBRALES", "VER_DASHBOARD", "GESTIONAR_ALERTAS", "VER_REPORTES", "GESTIONAR_USUARIOS"]
PERMISOS_TECNICO = ["VER_DASHBOARD", "GESTIONAR_ALERTAS", "VER_REPORTES"]


async def sembrar_datos() -> None:
    """Idempotente: crea roles y el administrador inicial si no existen."""
    async with SessionLocal() as db:
        for nombre, permisos in (("Administrador TI", PERMISOS_ADMIN), ("Equipo Tecnico", PERMISOS_TECNICO)):
            if not await db.scalar(select(Rol).where(Rol.nombre_rol == nombre)):
                db.add(Rol(nombre_rol=nombre, permisos=permisos))
        await db.flush()
        if not await db.scalar(select(Usuario).limit(1)):
            rol = await db.scalar(select(Rol).where(Rol.nombre_rol == "Administrador TI"))
            db.add(Usuario(username=settings.admin_username, email=settings.admin_email,
                           password_hash=hash_password(settings.admin_password), rol_id=rol.id))
            log.warning("Usuario administrador inicial '%s' creado. Cambia su contraseña.", settings.admin_username)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.jwt_secret == "CAMBIAR-EN-PRODUCCION":
        log.warning("JWT_SECRET usa el valor por defecto: NO usar así en producción")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # no-op si db/schema.sql ya creó las tablas
    await sembrar_datos()
    if settings.scheduler_enabled:
        planificador.iniciar()
    yield
    await planificador.detener()
    await engine.dispose()


app = FastAPI(title="Sistema de Monitoreo Proactivo y Alerta Temprana", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, dispositivos.router, umbrales.router, alertas.router, dashboard.router,
          reportes.router, usuarios.router):
    app.include_router(r, prefix="/api")
