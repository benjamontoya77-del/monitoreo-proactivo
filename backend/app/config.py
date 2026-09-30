from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://monitor:monitor@localhost:5432/monitoreo"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Seguridad (RNF1: RBAC + JWT)
    jwt_secret: str = "CAMBIAR-EN-PRODUCCION"
    jwt_algoritmo: str = "HS256"
    jwt_minutos: int = 480
    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = "Cambiar.123"

    # Motor de escaneo (RF1)
    scheduler_enabled: bool = True
    tick_segundos: int = 5
    max_concurrentes: int = 50
    ping_timeout_s: int = 2
    ping_intentos: int = 2
    snmp_timeout_s: int = 2
    http_timeout_s: int = 5
    retencion_dias: int = 30
    sla_objetivo_pct: float = 99.0

    # Alertas (RF3): Telegram principal, SMTP como respaldo (riesgo 3.3.1)
    telegram_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""  # varios destinatarios separados por coma


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
