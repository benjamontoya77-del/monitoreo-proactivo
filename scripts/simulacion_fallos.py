#!/usr/bin/env python3
"""Simulación de fallos (Hito 2, 3.3.3) — valida el criterio de éxito del Hito 1:
   'Detección de al menos el 95% de fallos simulados con < 1 min de retraso'.

Registra nodos con IPs del bloque TEST-NET-1 (192.0.2.0/24, RFC 5737: nunca responden,
equivalen a un servicio caído), mide cuántos segundos tarda el sistema en abrir la alerta,
y calcula el porcentaje detectado a tiempo. No usa dependencias externas.

Uso:  python scripts/simulacion_fallos.py --url http://localhost:8000 --user admin --password '...' --n 10
"""
import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request


def http(url, method="GET", token=None, body=None, form=None):
    data, headers = None, {}
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--n", type=int, default=10, help="cantidad de fallos a simular")
    ap.add_argument("--frecuencia", type=int, default=15, help="frecuencia de escaneo del nodo (s)")
    ap.add_argument("--limite", type=int, default=60, help="tiempo máximo aceptable de detección (s)")
    a = ap.parse_args()
    api = a.url.rstrip("/") + "/api"
    token = http(f"{api}/auth/login", "POST", form={"username": a.user, "password": a.password})["access_token"]

    creados, tiempos = [], {}
    t0 = time.time()
    for i in range(a.n):
        n = http(f"{api}/dispositivos", "POST", token, {
            "nombre": f"SIM_FALLA_{i+1}", "ip": f"192.0.2.{100+i}", "tipo_dispositivo": "Servidor",
            "frecuencia_segundos": a.frecuencia})
        creados.append(n["id"])
    print(f"{a.n} nodos caídos simulados registrados. Esperando detección (máx. {a.limite*3}s)...")

    while time.time() - t0 < a.limite * 3 and len(tiempos) < a.n:
        for al in http(f"{api}/alertas?estado=ABIERTA&limit=500", token=token):
            if al["dispositivo_id"] in creados and al["dispositivo_id"] not in tiempos:
                tiempos[al["dispositivo_id"]] = time.time() - t0
        time.sleep(1)

    a_tiempo = sum(1 for t in tiempos.values() if t < a.limite)
    pct = a_tiempo / a.n * 100
    print(f"\nDetectados: {len(tiempos)}/{a.n} | a tiempo (<{a.limite}s): {a_tiempo}/{a.n} = {pct:.1f}%")
    if tiempos:
        print(f"Tiempo de detección  min={min(tiempos.values()):.1f}s  prom={statistics.mean(tiempos.values()):.1f}s  máx={max(tiempos.values()):.1f}s")
    print("CRITERIO (>=95% con <1 min):", "CUMPLIDO ✅" if pct >= 95 else "NO CUMPLIDO ❌")

    for i in creados:  # limpieza
        http(f"{api}/dispositivos/{i}", "DELETE", token)


if __name__ == "__main__":
    main()
