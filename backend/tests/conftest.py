import os
import tempfile

# Debe fijarse ANTES de importar la aplicación
_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{_db}",
    "SCHEDULER_ENABLED": "false",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "Admin.12345",
    "JWT_SECRET": "secreto-de-pruebas",
    "TELEGRAM_TOKEN": "", "SMTP_HOST": "",
})

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import monitor, notifier
from app.services.scanner import Resultado


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "Admin.12345"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def escaner_falso(monkeypatch):
    """Sustituye el escáner real por uno controlable + captura las notificaciones enviadas."""
    estado = {"resultado": Resultado(disponible=True, latencia_ms=10), "mensajes": []}

    async def falso(_disp):
        return estado["resultado"]

    async def captura(texto, asunto=""):
        estado["mensajes"].append(texto)
        return True

    monkeypatch.setattr(monitor, "escanear", falso)
    monkeypatch.setattr(notifier, "notificar", captura)
    return estado
