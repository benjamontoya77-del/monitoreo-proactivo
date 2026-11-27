"""Notificaciones: Telegram (principal) con respaldo SMTP y envíos dirigidos por usuario."""
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


def _smtp_sync(
    asunto: str,
    texto: str,
    destinatario: str | None = None,
    adjunto_nombre: str | None = None,
    adjunto_bytes: bytes | None = None,
    maintype: str = "application",
    subtype: str = "octet-stream",
) -> None:
    destino = (destinatario or settings.smtp_to or "").strip()
    if not settings.smtp_host or not destino:
        raise ValueError("Servidor SMTP o correo destinatario no configurado")

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = destino
    msg.set_content(texto)

    if adjunto_nombre and adjunto_bytes is not None:
        msg.add_attachment(
            adjunto_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=adjunto_nombre,
        )

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


def canal_smtp_configurado(destinatario: str | None = None) -> bool:
    destino = (destinatario or settings.smtp_to or "").strip()
    return bool(settings.smtp_host and destino)


async def notificar(
    texto: str,
    asunto: str = "Alerta de monitoreo",
    destinatario: str | None = None,
) -> str | None:
    """Para alertas del motor: nunca lanza excepciones. Retorna 'Telegram', 'SMTP' o None."""
    if not destinatario and canal_telegram_configurado():
        try:
            await _telegram(texto)
            return "Telegram"
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram falló (%s); intentando SMTP", type(e).__name__)

    if canal_smtp_configurado(destinatario):
        try:
            await asyncio.to_thread(_smtp_sync, asunto, texto, destinatario)
            return "SMTP"
        except Exception as e:  # noqa: BLE001
            log.error("SMTP falló: %s", e)
    else:
        log.info("Sin canal de notificación configurado. Mensaje: %s", texto)

    return None


async def enviar_correo_usuario(
    destinatario: str,
    asunto: str,
    texto: str,
    adjunto_nombre: str | None = None,
    adjunto_bytes: bytes | None = None,
    maintype: str = "application",
    subtype: str = "octet-stream",
    silencioso: bool = False,
) -> bool:
    """Envía un correo directo exclusivamente al correo del usuario indicado."""
    if not canal_smtp_configurado(destinatario):
        if silencioso:
            log.warning("SMTP no configurado para enviar aviso a %s", destinatario)
            return False
        raise RuntimeError("El servidor SMTP no está configurado o el usuario no tiene correo registrado.")

    try:
        await asyncio.to_thread(
            _smtp_sync,
            asunto,
            texto,
            destinatario,
            adjunto_nombre,
            adjunto_bytes,
            maintype,
            subtype,
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Error enviando correo a %s: %s", destinatario, e)
        if silencioso:
            return False
        raise RuntimeError(f"No se pudo enviar el correo a {destinatario}: {e}") from e