"""Modelo relacional (Hito 2, 3.6.6). Debe mantenerse alineado con db/schema.sql."""
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# ARRAY nativo en PostgreSQL; JSON en SQLite (solo se usa en las pruebas).
PermList = JSON().with_variant(ARRAY(String(255)), "postgresql")
BigPK = BigInteger().with_variant(Integer, "sqlite")


def ahora() -> datetime:
    """UTC 'naive' (coincide con TIMESTAMP sin zona de la BD)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Rol(Base):
    __tablename__ = "rol"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_rol: Mapped[str] = mapped_column(String(100), unique=True)
    permisos: Mapped[list] = mapped_column(PermList)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id", ondelete="RESTRICT"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    rol: Mapped[Rol] = relationship(lazy="joined")


class Dispositivo(Base):
    __tablename__ = "dispositivo"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255))
    ip: Mapped[str] = mapped_column(String(15), unique=True)
    tipo_dispositivo: Mapped[str] = mapped_column(String(50))
    comunidad_snmp: Mapped[str] = mapped_column(String(255), default="public")
    snmp_habilitado: Mapped[bool] = mapped_column(Boolean, default=False)
    url_http: Mapped[str | None] = mapped_column(String(500), nullable=True)
    frecuencia_segundos: Mapped[int] = mapped_column(Integer, default=60)
    estado_actual: Mapped[str] = mapped_column(String(50), default="ACTIVO")


class ReglaUmbral(Base):
    __tablename__ = "regla_umbral"
    id: Mapped[int] = mapped_column(primary_key=True)
    dispositivo_id: Mapped[int] = mapped_column(ForeignKey("dispositivo.id", ondelete="CASCADE"))
    parametro: Mapped[str] = mapped_column(String(100))
    valor_umbral: Mapped[float] = mapped_column(Float)
    criticidad: Mapped[str] = mapped_column(String(50))
    habilitada: Mapped[bool] = mapped_column(Boolean, default=True)


class MetricaHistorico(Base):
    __tablename__ = "metrica_historico"
    __table_args__ = (Index("idx_metrica_dispositivo_time", "dispositivo_id", "timestamp"),)
    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    dispositivo_id: Mapped[int] = mapped_column(ForeignKey("dispositivo.id", ondelete="CASCADE"))
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uso_cpu_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    uso_ram_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    interfaces_down: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disponible: Mapped[bool] = mapped_column(Boolean, default=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class AlertaLog(Base):
    __tablename__ = "alerta_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    dispositivo_id: Mapped[int] = mapped_column(ForeignKey("dispositivo.id", ondelete="CASCADE"))
    regla_id: Mapped[int] = mapped_column(ForeignKey("regla_umbral.id", ondelete="CASCADE"))
    descripcion: Mapped[str] = mapped_column(String(255))
    fecha_hora_creacion: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fecha_hora_resolucion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estado_alerta: Mapped[str] = mapped_column(String(50), default="ABIERTA")


class AuditoriaAcceso(Base):
    __tablename__ = "auditoria_acceso"
    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    accion: Mapped[str] = mapped_column(String(50))
    detalle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_origen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
