"""Planificador en segundo plano: escanea cada dispositivo según su `frecuencia_segundos`."""
import asyncio
import logging
import time
from datetime import timedelta

from sqlalchemy import delete, select

from ..config import settings
from ..database import SessionLocal
from ..models import Dispositivo, MetricaHistorico, ahora
from . import monitor

log = logging.getLogger("planificador")


class Planificador:
    def __init__(self) -> None:
        self._ultimo: dict[int, float] = {}
        self._en_curso: set[int] = set()
        self._sem = asyncio.Semaphore(settings.max_concurrentes)
        self._task: asyncio.Task | None = None
        self._ultima_purga = 0.0

    def iniciar(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def detener(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while True:
            try:
                await self.tick()
                await self._purgar()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("Error en el ciclo de escaneo")
            await asyncio.sleep(settings.tick_segundos)

    async def tick(self) -> None:
        async with SessionLocal() as db:
            devs = (await db.execute(select(Dispositivo.id, Dispositivo.frecuencia_segundos))).all()
        ahora_m = time.monotonic()
        for dev_id, frec in devs:
            if dev_id in self._en_curso or ahora_m - self._ultimo.get(dev_id, float("-inf")) < frec:
                continue
            self._ultimo[dev_id] = ahora_m
            asyncio.create_task(self.escanear(dev_id))

    async def escanear(self, dev_id: int) -> None:
        if dev_id in self._en_curso:
            return
        self._en_curso.add(dev_id)
        try:
            async with self._sem, SessionLocal() as db:
                disp = await db.get(Dispositivo, dev_id)
                if disp:
                    await monitor.escanear_y_procesar(db, disp)
        except Exception:  # noqa: BLE001
            log.exception("Fallo al escanear el dispositivo %s", dev_id)
        finally:
            self._en_curso.discard(dev_id)

    async def escanear_todos(self) -> None:
        async with SessionLocal() as db:
            ids = (await db.scalars(select(Dispositivo.id))).all()
        await asyncio.gather(*(self.escanear(i) for i in ids))

    async def _purgar(self) -> None:
        """Retención: elimina métricas antiguas una vez al día."""
        if time.monotonic() - self._ultima_purga < 86400:
            return
        self._ultima_purga = time.monotonic()
        limite = ahora() - timedelta(days=settings.retencion_dias)
        async with SessionLocal() as db:
            await db.execute(delete(MetricaHistorico).where(MetricaHistorico.timestamp < limite))
            await db.commit()


planificador = Planificador()
