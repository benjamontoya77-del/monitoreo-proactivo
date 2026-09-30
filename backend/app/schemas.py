import ipaddress
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PARAMETROS = ("latencia_ms", "uso_cpu_pct", "uso_ram_pct", "interfaces_down", "disponibilidad")
Parametro = Literal["latencia_ms", "uso_cpu_pct", "uso_ram_pct", "interfaces_down", "disponibilidad"]
Criticidad = Literal["Alta", "Crítica"]
# La comunidad se pasa como argumento a snmpget: se prohíbe que empiece con '-' o tenga espacios.
COMUNIDAD_RE = r"^[^\s\-][^\s]{0,63}$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth / usuarios -------------------------------------------------------
class UsuarioOut(ORM):
    id: int
    username: str
    email: str
    activo: bool
    rol: str
    permisos: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class UsuarioCrear(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=72)
    rol_id: int


class UsuarioActualizar(BaseModel):
    activo: bool | None = None
    rol_id: int | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


# ---- dispositivos ----------------------------------------------------------
class DispositivoBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    ip: str
    tipo_dispositivo: Literal["Switch", "Servidor", "Router", "Firewall"]
    comunidad_snmp: str = Field(default="public", pattern=COMUNIDAD_RE)
    snmp_habilitado: bool = False
    url_http: str | None = Field(default=None, pattern=r"^https?://\S+$", max_length=500)
    frecuencia_segundos: int = Field(default=60, ge=5, le=86400)

    @field_validator("ip")
    @classmethod
    def ipv4(cls, v: str) -> str:
        try:
            return str(ipaddress.IPv4Address(v.strip()))
        except ValueError:
            raise ValueError("Dirección IPv4 inválida")


class DispositivoCrear(DispositivoBase):
    pass


class DispositivoActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    tipo_dispositivo: Literal["Switch", "Servidor", "Router", "Firewall"] | None = None
    comunidad_snmp: str | None = Field(default=None, pattern=COMUNIDAD_RE)
    snmp_habilitado: bool | None = None
    url_http: str | None = Field(default=None, pattern=r"^https?://\S+$", max_length=500)
    frecuencia_segundos: int | None = Field(default=None, ge=5, le=86400)


class DispositivoOut(ORM):
    id: int
    nombre: str
    ip: str
    tipo_dispositivo: str
    comunidad_snmp: str
    snmp_habilitado: bool
    url_http: str | None
    frecuencia_segundos: int
    estado_actual: str


# ---- umbrales --------------------------------------------------------------
class UmbralCrear(BaseModel):
    dispositivo_id: int
    parametro: Parametro
    valor_umbral: float
    criticidad: Criticidad = "Alta"
    habilitada: bool = True


class UmbralActualizar(BaseModel):
    valor_umbral: float | None = None
    criticidad: Criticidad | None = None
    habilitada: bool | None = None


class UmbralOut(ORM):
    id: int
    dispositivo_id: int
    parametro: str
    valor_umbral: float
    criticidad: str
    habilitada: bool


# ---- métricas / alertas ----------------------------------------------------
class MetricaOut(ORM):
    id: int
    dispositivo_id: int
    latencia_ms: int | None
    uso_cpu_pct: float | None
    uso_ram_pct: float | None
    interfaces_down: int | None
    http_status: int | None
    disponible: bool
    timestamp: datetime


class AlertaOut(BaseModel):
    id: int
    dispositivo_id: int
    nodo: str
    ip: str
    parametro: str
    criticidad: str
    descripcion: str
    estado_alerta: str
    fecha_hora_creacion: datetime
    fecha_hora_resolucion: datetime | None
    duracion_s: int | None
