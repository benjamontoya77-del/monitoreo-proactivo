# Sistema de Monitoreo Proactivo y Alerta Temprana

Proyecto de título — Benjamín Montoya Fuentes. Implementación del diseño de los Hitos 1, 2 y 3.
100 % software libre: **FastAPI · PostgreSQL 17 · React + ApexCharts · Pytest · net-snmp · Docker**.

## Arranque rápido (Docker)

```bash
cp .env.example .env        # edita JWT_SECRET, ADMIN_PASSWORD, DB_PASSWORD y (opcional) Telegram/SMTP
docker compose up --build
```
- Dashboard: http://localhost:8080  (usuario/clave = `ADMIN_USERNAME` / `ADMIN_PASSWORD`)
- API + documentación Swagger: http://localhost:8000/docs

## Ejecución local sin Docker (Windows/Linux)

```bash
# 1) PostgreSQL local con la BD creada:  createdb monitoreo  &&  psql monitoreo -f db/schema.sql
# 2) Backend
cd backend && python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://USUARIO:CLAVE@localhost:5432/monitoreo   # (o archivo backend/.env)
uvicorn app.main:app --reload
# 3) Frontend
cd ../frontend && npm install && npm run dev      # http://localhost:5173 (proxy a :8000)
```
Para SNMP instala net-snmp (`apt install snmp`; en Windows: net-snmp o WSL). Para ICMP se usa el `ping` del sistema.

## Trazabilidad con los Hitos

| Requisito (Hito) | Implementación |
|---|---|
| RF1 Escaneos cíclicos de disponibilidad | `services/planificador.py` (frecuencia por nodo, concurrente) + `services/scanner.py` (ICMP) |
| RF2 Centralización de logs y métricas CPU/RAM | Tabla `metrica_historico`, `alerta_log`, `auditoria_acceso`; SNMP v2c en `scanner.py` |
| RF3 Notificación en tiempo real | `services/notifier.py`: Telegram (principal) → SMTP (respaldo, riesgo 3.3.1) |
| RNF1 RBAC | Tablas `rol`/`usuario`, JWT + bcrypt, dependencia `requiere(permiso)` en `deps.py` |
| RNF2 Interfaz responsiva y proactiva | `frontend/` (React, refresco cada 5 s, ApexCharts) |
| RNF3 Solo software libre | Ver stack; ninguna licencia comercial |
| ICMP / SNMP / HTTP-S (alcance Hito 1) | `scanner.py`: `ping`, `snmpget/snmpwalk` (CPU, RAM, interfaces), `httpx` |
| Módulo Administración (usuarios, nodos, auditoría) | `routers/usuarios.py`, `routers/dispositivos.py`, `/api/auditoria` |
| Motor de reglas proactivo / umbrales | `services/reglas.py`, `routers/umbrales.py` |
| Dashboard tiempo real (Status Board) | `pages/Dashboard.jsx` |
| Reportabilidad: SLA, gráficos, historial | `services/sla.py`, `/api/reportes/*` (+CSV), `pages/Reportes.jsx` |
| Pruebas: unidad, integración, simulación de fallos (3.3.3) | `backend/tests/` y `scripts/simulacion_fallos.py` |
| Métrica: ≥95 % fallos detectados en < 1 min | `scripts/simulacion_fallos.py` mide y reporta el porcentaje |

**Anti-fatiga de alertas:** una regla no vuelve a abrir alerta mientras ya tenga una abierta; solo se notifica al abrir y al resolver.

## Pruebas

```bash
cd backend && pytest -v            # unidad (reglas, ping, SNMP, SLA) + integración API/BD con SQLite
python scripts/simulacion_fallos.py --url http://localhost:8000 --password 'TU_CLAVE' --n 10
```
La simulación usa IPs `192.0.2.x` (RFC 5737, nunca responden): equivale a apagar servicios y mide el tiempo real hasta la alerta.

## Telegram
1. En Telegram habla con **@BotFather** → `/newbot` → copia el token a `TELEGRAM_TOKEN`.
2. Escríbele un mensaje a tu bot y abre `https://api.telegram.org/bot<TOKEN>/getUpdates` para leer tu `chat.id` → `TELEGRAM_CHAT_ID`.

## Probar SNMP
En un servidor Linux a monitorear: `apt install snmpd`, en `/etc/snmp/snmpd.conf` define `rocommunity TU_COMUNIDAD IP_DEL_MONITOR` y `systemctl restart snmpd`.
Verifica con `snmpget -v2c -c TU_COMUNIDAD IP 1.3.6.1.4.1.2021.11.11.0`. Luego marca el nodo con SNMP habilitado en el dashboard.

## Cambios respecto al esquema del Hito 2 
- Nueva tabla **`auditoria_acceso`** (módulo "Auditoría de Acceso" de tu EDT) → el modelo queda en 7 tablas.
- `dispositivo`: `snmp_habilitado`, `url_http`. `metrica_historico`: `interfaces_down`, `http_status`, `disponible` (base del Uptime).
- Parámetros de `regla_umbral`: además de latencia/CPU/RAM, `interfaces_down` y `disponibilidad` (regla crítica creada automáticamente por nodo).
- Se retiró el hash de contraseña escrito a mano del SQL de semilla: el admin se crea desde `.env` al primer arranque.
- `dispositivo.estado_actual` = ACTIVO / ALERTA / CRÍTICO (calculado por el motor).

## Consideraciones Técnicas y Trabajo Futuro
- Uptime = % de muestras disponibles (aproximación por muestreo, precisión ligada a la frecuencia de escaneo).
- SNMP solo v2c (como declara tu alcance); IPv4 únicamente (columna `VARCHAR(15)`).
- Cierre manual de una alerta con la falla aún activa: el motor la reabre en el siguiente ciclo.
- No hay límite de intentos de login (rate limiting) ni HTTPS propio: en producción ponlo detrás de un proxy TLS (Caddy/Nginx) y restringe el puerto 8000.
- Sin migraciones Alembic: `db/schema.sql` crea la BD en la primera instalación.
