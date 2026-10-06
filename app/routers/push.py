"""Suscripcion a notificaciones push del navegador (Web Push estandar).

Cualquier usuario logueado (recibo/piso/admin) puede activar notificaciones
en su propio dispositivo -- no hace falta ser admin para esto.
"""
import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.database import get_db
from app.deps import require_login

router = APIRouter()


@router.get("/push/vapid-public-key", response_class=PlainTextResponse)
def vapid_public_key(db: sqlite3.Connection = Depends(get_db), user=Depends(require_login)):
    row = db.execute("SELECT value FROM settings WHERE key = 'vapid_public_key'").fetchone()
    return row["value"] if row else ""


@router.post("/push/subscribe")
async def subscribe(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_login),
):
    data = await request.json()
    endpoint = data.get("endpoint")
    keys = data.get("keys", {})
    if not endpoint or "p256dh" not in keys or "auth" not in keys:
        return JSONResponse({"ok": False, "error": "Suscripcion incompleta"}, status_code=400)

    db.execute(
        "INSERT INTO push_subscriptions (endpoint, p256dh, auth, usuario_id) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth",
        (endpoint, keys["p256dh"], keys["auth"], user["id"]),
    )
    db.commit()
    return JSONResponse({"ok": True})
