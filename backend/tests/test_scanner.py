"""Pruebas de unidad: cálculo/parseo de latencia y métricas SNMP (Hito 2, 3.3.3)."""
import asyncio

import pytest

from app.services import scanner


def test_parseo_ping_linux():
    out = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=14.3 ms"
    assert scanner.parsear_latencia_ping(out) == 14


def test_parseo_ping_windows_espanol_e_ingles():
    assert scanner.parsear_latencia_ping("Respuesta desde 8.8.8.8: bytes=32 tiempo=23ms TTL=117") == 23
    assert scanner.parsear_latencia_ping("Reply from 127.0.0.1: bytes=32 time<1ms TTL=128") == 1


def test_parseo_ping_sin_respuesta():
    assert scanner.parsear_latencia_ping("Request timed out.") is None


def test_ping_rechaza_ip_invalida():
    with pytest.raises(ValueError):
        asyncio.run(scanner.ping("8.8.8.8; rm -rf /"))


def _falso_snmp(respuestas):
    async def f(cmd, com, ip, *oids):
        return respuestas.get((cmd, oids[0]), [])
    return f


def test_snmp_cpu_desde_ucd(monkeypatch):
    monkeypatch.setattr(scanner, "_snmp", _falso_snmp({("snmpget", scanner.OID_CPU_IDLE): ["72"]}))
    assert asyncio.run(scanner.snmp_cpu("10.0.0.1", "public")) == 28.0


def test_snmp_cpu_fallback_hrprocessor(monkeypatch):
    monkeypatch.setattr(scanner, "_snmp", _falso_snmp({
        ("snmpget", scanner.OID_CPU_IDLE): ["No Such Object available on this agent at this OID"],
        ("snmpwalk", scanner.OID_HR_CPU): ["10", "30"]}))
    assert asyncio.run(scanner.snmp_cpu("10.0.0.1", "public")) == 20.0


def test_snmp_ram(monkeypatch):
    # total 1000 kB, libre 200, buffers 100, cache 100 -> usada 600 = 60 %
    monkeypatch.setattr(scanner, "_snmp", _falso_snmp({("snmpget", scanner.OID_MEM[0]): ["1000", "200", "100", "100"]}))
    assert asyncio.run(scanner.snmp_ram("10.0.0.1", "public")) == 60.0


def test_snmp_interfaces_down_ignora_puertos_apagados_por_admin(monkeypatch):
    monkeypatch.setattr(scanner, "_snmp", _falso_snmp({
        ("snmpwalk", scanner.OID_IF_ADMIN): ["up", "up", "down", "up"],
        ("snmpwalk", scanner.OID_IF_OPER): ["up", "down", "down", "down"]}))
    assert asyncio.run(scanner.snmp_interfaces_down("10.0.0.1", "public")) == 2


def test_escaneo_ip_inalcanzable_es_no_disponible(monkeypatch):
    async def sin_respuesta(ip):
        return None
    monkeypatch.setattr(scanner, "ping", sin_respuesta)
    d = type("D", (), dict(ip="192.0.2.99", url_http=None, snmp_habilitado=False, comunidad_snmp="public"))()
    r = asyncio.run(scanner.escanear_dispositivo(d))
    assert r.disponible is False and r.latencia_ms is None
