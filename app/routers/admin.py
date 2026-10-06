"""Admin: umbrales de alerta y alta de usuarios."""
import io
import secrets
import sqlite3

import qrcode
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.alerts import get_thresholds
from app.database import get_db
from app.deps import require_role
from app.security import hash_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin")
def admin_home(request: Request, db: sqlite3.Connection = Depends(get_db), user=Depends(require_role("admin"))):
    dias_amarillo, dias_rojo = get_thresholds(db)
    teams_webhook_url = db.execute(
        "SELECT value FROM settings WHERE key = 'teams_webhook_url'"
    ).fetchone()["value"]
    usuarios = db.execute(
        "SELECT id, username, role FROM users WHERE estado = 'activo' ORDER BY username"
    ).fetchall()
    pendientes = db.execute(
        "SELECT id, username, role FROM users WHERE estado = 'pendiente' ORDER BY username"
    ).fetchall()
    piso1_token = db.execute(
        "SELECT value FROM settings WHERE key = 'piso1_token'"
    ).fetchone()["value"]
    piso1_url = f"{request.base_url}piso1?token={piso1_token}"
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "user": user,
            "dias_amarillo": dias_amarillo,
            "dias_rojo": dias_rojo,
            "teams_webhook_url": teams_webhook_url,
            "usuarios": usuarios,
            "pendientes": pendientes,
            "piso1_url": piso1_url,
            "mensaje": None,
        },
    )


@router.post("/admin/settings")
def update_settings(
    dias_amarillo: int = Form(...),
    dias_rojo: int = Form(...),
    teams_webhook_url: str = Form(""),
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("admin")),
):
    db.execute("UPDATE settings SET value = ? WHERE key = 'dias_amarillo'", (str(dias_amarillo),))
    db.execute("UPDATE settings SET value = ? WHERE key = 'dias_rojo'", (str(dias_rojo),))
    db.execute("UPDATE settings SET value = ? WHERE key = 'teams_webhook_url'", (teams_webhook_url.strip(),))
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/usuarios")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("admin")),
):
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, hash_password(password), role),
    )
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/aprobar/{user_id}")
def aprobar_usuario(
    user_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("admin")),
):
    db.execute("UPDATE users SET estado = 'activo' WHERE id = ?", (user_id,))
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/rechazar/{user_id}")
def rechazar_usuario(
    user_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("admin")),
):
    db.execute("DELETE FROM users WHERE id = ? AND estado = 'pendiente'", (user_id,))
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/piso1/regenerar")
def regenerar_piso1_token(
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """Invalida el QR de piso1 actual y emite uno nuevo. Usalo si el QR
    viejo se perdio, se compartio fuera de la tienda, o nomas por rutina.
    """
    db.execute(
        "UPDATE settings SET value = ? WHERE key = 'piso1_token'",
        (secrets.token_urlsafe(16),),
    )
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/piso1/qr.png")
def piso1_qr(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("admin")),
):
    token = db.execute("SELECT value FROM settings WHERE key = 'piso1_token'").fetchone()["value"]
    url = f"{request.base_url}piso1?token={token}"
    buffer = io.BytesIO()
    qrcode.make(url).save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")
