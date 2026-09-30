"""Motor de escaneo: ICMP (ping), SNMP v2c (net-snmp) y HTTP/S. Todo asíncrono (RF1, RF2).

Se usan herramientas estándar y de código abierto del sistema (ping, snmpget/snmpwalk)
en lugar de sockets raw, para no requerir privilegios de root y evitar dependencias frágiles.
"""
import asyncio
import ipaddress
import logging
import re
import sys
import time
from dataclasses import dataclass

import httpx

from ..config import settings

log = logging.getLogger("scanner")


@dataclass
class Resultado:
    disponible: bool
    latencia_ms: int | None = None
    cpu: float | None = None
    ram: float | None = None
    interfaces_down: int | None = None
    http_status: int | None = None
    error: str | None = None


# ------------------------------- ICMP ---------------------------------------
_PING_RE = re.compile(r"(?:time|tiempo)\s*[=<]\s*([\d.,]+)", re.I)


def parsear_latencia_ping(salida: str) -> int | None:
    """Extrae el RTT en ms de la salida de ping (Linux/macOS/Windows, inglés o español)."""
    m = _PING_RE.search(salida)
    if not m:
        return None
    return max(1, round(float(m.group(1).replace(",", "."))))  # resolución de 1 ms


def _cmd_ping(ip: str, timeout_s: int) -> list[str]:
    if sys.platform.startswith("win"):
        return ["ping", "-n", "1", "-w", str(timeout_s * 1000), ip]
    if sys.platform == "darwin":
        return ["ping", "-c", "1", "-W", str(timeout_s * 1000), ip]
    return ["ping", "-c", "1", "-W", str(timeout_s), ip]


async def ping(ip: str) -> int | None:
    ipaddress.IPv4Address(ip)  # valida: nunca se ejecuta con texto arbitrario
    for _ in range(settings.ping_intentos):
        try:
            proc = await asyncio.create_subprocess_exec(
                *_cmd_ping(ip, settings.ping_timeout_s),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        except FileNotFoundError:
            raise RuntimeError("El comando 'ping' no está instalado en el servidor")
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), settings.ping_timeout_s + 3)
        except asyncio.TimeoutError:
            proc.kill()
            continue
        if proc.returncode == 0:
            lat = parsear_latencia_ping(out.decode(errors="ignore"))
            if lat is not None:
                return lat
    return None


# ------------------------------- SNMP ---------------------------------------
OID_CPU_IDLE = "1.3.6.1.4.1.2021.11.11.0"        # UCD-SNMP ssCpuIdle (%)
OID_HR_CPU = "1.3.6.1.2.1.25.3.3.1.2"            # HOST-RESOURCES hrProcessorLoad
OID_MEM = ["1.3.6.1.4.1.2021.4.5.0",             # memTotalReal (kB)
           "1.3.6.1.4.1.2021.4.6.0",             # memAvailReal
           "1.3.6.1.4.1.2021.4.14.0",            # memBuffer
           "1.3.6.1.4.1.2021.4.15.0"]            # memCached
OID_IF_ADMIN = "1.3.6.1.2.1.2.2.1.7"             # ifAdminStatus
OID_IF_OPER = "1.3.6.1.2.1.2.2.1.8"              # ifOperStatus


async def _snmp(cmd: str, comunidad: str, ip: str, *oids: str) -> list[str]:
    ipaddress.IPv4Address(ip)
    args = [cmd, "-v2c", "-c", comunidad, "-t", str(settings.snmp_timeout_s), "-r", "1", "-Oqv", ip, *oids]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), (settings.snmp_timeout_s + 1) * 2 + 5)
    except (asyncio.TimeoutError, FileNotFoundError):
        return []
    if proc.returncode != 0:
        return []
    return [l.strip().strip('"') for l in out.decode(errors="ignore").splitlines() if l.strip()]


def _num(txt: str) -> float | None:
    try:
        return float(txt)
    except (TypeError, ValueError):  # "No Such Object...", "Timeout"...
        return None


def _estado_if(v: str) -> str:
    v = v.lower()
    if v.startswith("up") or v == "1":
        return "up"
    if v.startswith("down") or v == "2":
        return "down"
    return "otro"


async def snmp_cpu(ip: str, com: str) -> float | None:
    v = await _snmp("snmpget", com, ip, OID_CPU_IDLE)
    idle = _num(v[0]) if v else None
    if idle is not None:
        return round(min(100.0, max(0.0, 100.0 - idle)), 1)
    cargas = [_num(x) for x in await _snmp("snmpwalk", com, ip, OID_HR_CPU)]
    cargas = [c for c in cargas if c is not None]
    return round(sum(cargas) / len(cargas), 1) if cargas else None


async def snmp_ram(ip: str, com: str) -> float | None:
    v = await _snmp("snmpget", com, ip, *OID_MEM)
    nums = [_num(x) for x in v]
    if len(nums) < 2 or nums[0] in (None, 0) or nums[1] is None:
        return None
    total, avail = nums[0], nums[1]
    buffers = nums[2] if len(nums) > 2 and nums[2] is not None else 0
    cached = nums[3] if len(nums) > 3 and nums[3] is not None else 0
    usada = total - (avail + buffers + cached)
    return round(min(100.0, max(0.0, usada / total * 100)), 1)


async def snmp_interfaces_down(ip: str, com: str) -> int | None:
    admin, oper = await asyncio.gather(_snmp("snmpwalk", com, ip, OID_IF_ADMIN),
                                       _snmp("snmpwalk", com, ip, OID_IF_OPER))
    if not admin or len(admin) != len(oper):
        return None
    # Solo interfaces habilitadas administrativamente que están caídas (evita falsos positivos de puertos sin uso)
    return sum(1 for a, o in zip(admin, oper) if _estado_if(a) == "up" and _estado_if(o) == "down")


async def snmp_metricas(ip: str, com: str) -> tuple[float | None, float | None, int | None]:
    return tuple(await asyncio.gather(snmp_cpu(ip, com), snmp_ram(ip, com), snmp_interfaces_down(ip, com)))  # type: ignore


# ------------------------------- HTTP/S -------------------------------------
async def chequeo_http(url: str) -> tuple[int | None, int | None]:
    """Devuelve (codigo_http, ms). None si no hubo respuesta."""
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_s, follow_redirects=True) as c:
            r = await c.get(url)
        return r.status_code, max(1, round((time.perf_counter() - t0) * 1000))
    except httpx.HTTPError:
        return None, None


# ------------------------------- Orquestación -------------------------------
async def escanear_dispositivo(d) -> Resultado:
    """Sondea un dispositivo. `disponible` = HTTP 2xx/3xx si tiene url_http (disponibilidad del
    servicio); en caso contrario, respuesta ICMP."""
    try:
        lat, http = await asyncio.gather(
            ping(d.ip), chequeo_http(d.url_http) if d.url_http else _nada())
    except RuntimeError as e:
        log.error("%s", e)
        return Resultado(disponible=False, error=str(e))
    codigo, ms_http = http
    if d.url_http:
        disponible = codigo is not None and 200 <= codigo < 400
        latencia = lat if lat is not None else ms_http
    else:
        disponible, latencia = lat is not None, lat
    r = Resultado(disponible=disponible, latencia_ms=latencia, http_status=codigo)
    if d.snmp_habilitado and lat is not None:  # sin ICMP no se pierde tiempo esperando SNMP (fallback ICMP)
        r.cpu, r.ram, r.interfaces_down = await snmp_metricas(d.ip, d.comunidad_snmp)
    return r


async def _nada():
    return None, None
