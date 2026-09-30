"""Pruebas de integración API <-> BD <-> motor de reglas (Hito 2, 3.3.3) y simulación de fallos."""
import asyncio

from app.services.scanner import Resultado

NODO = {"nombre": "Web_Server_01", "ip": "192.0.2.99", "tipo_dispositivo": "Servidor", "frecuencia_segundos": 15}


def test_login_incorrecto(client):
    assert client.post("/api/auth/login", data={"username": "admin", "password": "mala"}).status_code == 401


def test_endpoints_protegidos(client):
    assert client.get("/api/dashboard").status_code == 401


def test_rbac_equipo_tecnico_no_puede_crear_nodos(client, admin_headers):
    roles = client.get("/api/roles", headers=admin_headers).json()
    rol_tec = next(r["id"] for r in roles if r["nombre_rol"] == "Equipo Tecnico")
    r = client.post("/api/usuarios", headers=admin_headers,
                    json={"username": "tecnico1", "email": "t1@x.cl", "password": "Tecnico.123", "rol_id": rol_tec})
    assert r.status_code == 201
    tok = client.post("/api/auth/login", data={"username": "tecnico1", "password": "Tecnico.123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/dashboard", headers=h).status_code == 200
    assert client.post("/api/dispositivos", headers=h, json=NODO).status_code == 403
    assert client.get("/api/usuarios", headers=h).status_code == 403


def test_validaciones_de_entrada(client, admin_headers):
    mala_ip = {**NODO, "ip": "999.1.1.1"}
    assert client.post("/api/dispositivos", headers=admin_headers, json=mala_ip).status_code == 422
    inyeccion = {**NODO, "ip": "10.9.9.9", "comunidad_snmp": "-v3 malicioso"}
    assert client.post("/api/dispositivos", headers=admin_headers, json=inyeccion).status_code == 422


def test_ciclo_completo_falla_alerta_y_recuperacion(client, admin_headers, escaner_falso):
    r = client.post("/api/dispositivos", headers=admin_headers, json=NODO)
    assert r.status_code == 201
    disp_id = r.json()["id"]
    assert client.post("/api/dispositivos", headers=admin_headers, json=NODO).status_code == 409  # IP duplicada

    # 1) servicio sano
    client.post("/api/scan", headers=admin_headers)
    assert client.get("/api/dashboard", headers=admin_headers).json()["incidentes"] == []

    # 2) SIMULACIÓN DE FALLA: el nodo deja de responder -> alerta crítica + notificación
    escaner_falso["resultado"] = Resultado(disponible=False)
    client.post("/api/scan", headers=admin_headers)
    dash = client.get("/api/dashboard", headers=admin_headers).json()
    assert len(dash["incidentes"]) == 1 and dash["incidentes"][0]["criticidad"] == "Crítica"
    assert next(n for n in dash["nodos"] if n["id"] == disp_id)["estado"] == "CRÍTICO"
    assert any("ALERTA CRÍTICA" in m for m in escaner_falso["mensajes"])

    # 3) escaneos repetidos NO duplican la alerta (anti fatiga)
    client.post("/api/scan", headers=admin_headers)
    assert len(client.get("/api/alertas?estado=ABIERTA", headers=admin_headers).json()) == 1

    # 4) recuperación automática -> alerta resuelta + notificación
    escaner_falso["resultado"] = Resultado(disponible=True, latencia_ms=12)
    client.post("/api/scan", headers=admin_headers)
    dash = client.get("/api/dashboard", headers=admin_headers).json()
    assert dash["incidentes"] == []
    assert next(n for n in dash["nodos"] if n["id"] == disp_id)["estado"] == "ACTIVO"
    assert any("RESUELTA" in m for m in escaner_falso["mensajes"])

    # 5) reportes
    sla = client.get("/api/reportes/sla?dias=1", headers=admin_headers).json()
    fila = next(n for n in sla["nodos"] if n["dispositivo_id"] == disp_id)
    assert fila["incidentes"] == 1 and fila["muestras"] >= 3 and 0 < fila["uptime_pct"] < 100
    assert client.get("/api/reportes/sla.csv", headers=admin_headers).text.startswith("nodo,ip")


def test_umbral_de_latencia_personalizado(client, admin_headers, escaner_falso):
    nodo = {**NODO, "nombre": "Switch_Core", "ip": "192.0.2.50", "tipo_dispositivo": "Switch"}
    disp_id = client.post("/api/dispositivos", headers=admin_headers, json=nodo).json()["id"]
    r = client.post("/api/umbrales", headers=admin_headers,
                    json={"dispositivo_id": disp_id, "parametro": "latencia_ms", "valor_umbral": 150, "criticidad": "Alta"})
    assert r.status_code == 201
    escaner_falso["resultado"] = Resultado(disponible=True, latencia_ms=320)
    client.post("/api/scan", headers=admin_headers)
    inc = [i for i in client.get("/api/dashboard", headers=admin_headers).json()["incidentes"] if i["dispositivo_id"] == disp_id]
    assert len(inc) == 1 and inc[0]["parametro"] == "latencia_ms"
    # cierre manual
    assert client.post(f"/api/alertas/{inc[0]['id']}/resolver", headers=admin_headers).status_code == 200


def test_auditoria_registra_accesos(client, admin_headers):
    acciones = {a["accion"] for a in client.get("/api/auditoria", headers=admin_headers).json()}
    assert {"LOGIN", "LOGIN_FALLIDO", "NODO_CREADO"} <= acciones
