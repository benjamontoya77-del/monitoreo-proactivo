"""Notificaciones: Telegram (principal) con respaldo SMTP (mitigación de riesgo 3.3.1)."""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from ..config import settings

log = logging.getLogger("notifier")


async def _telegram(texto: str) -> None:
    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, json={"chat_id": settings.telegram_chat_id, "text": texto})
        r.raise_for_status()


def _smtp_sync(asunto: str, texto: str) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"] = asunto, settings.smtp_from or settings.smtp_user
    msg["To"] = settings.smtp_to
    msg.set_content(texto)
    if settings.smtp_port == 465:
        srv = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
    else:
        srv = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        srv.starttls()
    with srv:
        if settings.smtp_user:
            srv.login(settings.smtp_user, settings.smtp_password)
        srv.send_message(msg)


def canal_telegram_configurado() -> bool:
    return bool(settings.telegram_token and settings.telegram_chat_id)


def canal_smtp_configurado() -> bool:
    return bool(settings.smtp_host and settings.smtp_to)


async def notificar(texto: str, asunto: str = "Alerta de monitoreo") -> bool:
    """Nunca lanza excepciones: una falla de mensajería no debe detener el monitoreo."""
    if canal_telegram_configurado():
        try:
            await _telegram(texto)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram falló (%s); intentando SMTP", type(e).__name__)
    if canal_smtp_configurado():
        try:
            await asyncio.to_thread(_smtp_sync, asunto, texto)
            return True
        except Exception as e:  # noqa: BLE001
            log.error("SMTP falló: %s", e)
    else:
        log.info("Sin canal de notificación configurado. Mensaje: %s", texto)
    return False
