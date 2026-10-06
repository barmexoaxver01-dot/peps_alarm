"""Flujo: alguien pide acceso -> admin lo ve pendiente -> aprueba/rechaza.

Corre contra una copia temporal de la base de datos (nunca toca
peps_alarm.db real) -- ver fixture `client` para el detalle.
"""
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import database  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """App completa apuntando a un .db temporal y desechable."""
    temp_db = tmp_path / "test_peps_alarm.db"
    monkeypatch.setattr(database, "DB_PATH", temp_db)
    database.init_db()

    import seed  # mismo bootstrap que usa /README.md, no lo reinventamos

    seed.main()

    from app.main import app  # import tardio: ya con DB_PATH parchado

    with TestClient(app) as test_client:
        yield test_client

    shutil.rmtree(tmp_path, ignore_errors=True)


def _login(client: TestClient, username: str, password: str) -> None:
    resp = client.post("/login", data={"username": username, "password": password})
    assert resp.status_code in (200, 303), resp.text


def test_solicitud_pendiente_aparece_y_se_puede_aprobar(client: TestClient):
    # 1. Alguien pide acceso -> queda 'pendiente', no puede loguearse todavia.
    resp = client.post(
        "/solicitar-acceso",
        data={"username": "nueva_persona", "password": "clave123", "role": "piso"},
    )
    assert resp.status_code == 200

    login_fallido = client.post(
        "/login", data={"username": "nueva_persona", "password": "clave123"}
    )
    assert login_fallido.status_code == 403
    assert "pendiente de aprobacion" in login_fallido.text.lower()

    # 2. El admin la ve en el panel (antes de este fix, esta seccion no existia).
    _login(client, "admin", "peps2024")
    admin_page = client.get("/admin")
    assert "nueva_persona" in admin_page.text
    assert "Solicitudes pendientes" in admin_page.text

    # 3. Aprobar -> ya puede entrar.
    import sqlite3

    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    user_id = conn.execute(
        "SELECT id FROM users WHERE username = 'nueva_persona'"
    ).fetchone()["id"]
    conn.close()

    aprobar = client.post(f"/admin/aprobar/{user_id}", follow_redirects=False)
    assert aprobar.status_code == 303

    login_ok = client.post(
        "/login", data={"username": "nueva_persona", "password": "clave123"},
        follow_redirects=False,
    )
    assert login_ok.status_code == 303
    assert login_ok.headers["location"] == "/dashboard"


def test_crear_usuario_duplicado_no_truena_muestra_error(client: TestClient):
    _login(client, "admin", "peps2024")

    primero = client.post(
        "/admin/usuarios",
        data={"username": "repetido", "password": "x", "role": "piso"},
        follow_redirects=False,
    )
    assert primero.status_code == 303

    # Antes de este fix esto tronaba con 500 (UNIQUE constraint sin manejar).
    segundo = client.post(
        "/admin/usuarios",
        data={"username": "repetido", "password": "y", "role": "recibo"},
    )
    assert segundo.status_code == 400
    assert "ya existe" in segundo.text.lower()
