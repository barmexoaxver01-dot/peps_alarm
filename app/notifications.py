"""Envio de alertas a un canal de Teams via webhook.

A proposito NO usamos Microsoft Graph API aqui -- eso necesitaria registrar
una app en Azure AD y pedir permisos admin, que es un proceso largo. Un
webhook de Teams (Incoming Webhook clasico, o un Workflow de "Post to a
channel when a webhook request is received") es autoservicio: la persona
dueña del canal genera una URL en un par de clics, sin IT de por medio.
Nuestro backend solo necesita hacer un POST ahi.
"""
import json
import sqlite3
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from pywebpush import WebPushException, webpush


def enviar_resumen_teams(webhook_url: str, lotes: list[dict]) -> dict:
    """Manda un resumen de productos urgentes/caducados a Teams.

    Returns {"ok": bool, "mensaje": str} -- nunca lanza excepcion, para que
    un webhook mal configurado no tumbe el dashboard.
    """
    if not webhook_url:
        return {"ok": False, "mensaje": "No hay URL de Teams configurada. Ve a Admin para agregarla."}

    if not lotes:
        texto = "PEPS ALARM: sin productos urgentes ni caducados ahorita. Todo en orden."
    else:
        lineas = [
            f"- {lote['nombre']} ({lote['barcode']}): {lote['estilo']['label']}, caduca {lote['fecha_caducidad']}"
            for lote in lotes
        ]
        texto = "PEPS ALARM - productos que necesitan atencion:\n" + "\n".join(lineas)

    payload = json.dumps({"text": texto}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                return {"ok": False, "mensaje": f"Teams respondio con error {response.status}."}
        return {"ok": True, "mensaje": f"Alerta enviada a Teams ({len(lotes)} productos)."}
    except urllib.error.URLError as exc:
        return {"ok": False, "mensaje": f"No se pudo enviar a Teams: {exc.reason}"}


def enviar_push_a_todos(db: sqlite3.Connection, lotes: list[dict]) -> dict:
    """Manda una notificacion push del navegador a cada dispositivo suscrito.

    Limpia solas las suscripciones que ya expiraron (cuando el navegador
    responde 404/410 -- significa que esa suscripcion ya no existe).
    """
    settings = {
        row["key"]: row["value"]
        for row in db.execute(
            "SELECT key, value FROM settings WHERE key IN "
            "('vapid_private_key', 'vapid_claim_email')"
        ).fetchall()
    }
    private_key = settings.get("vapid_private_key")
    claim_email = settings.get("vapid_claim_email", "mailto:admin@example.com")
    if not private_key:
        return {"ok": False, "mensaje": "No hay llaves VAPID generadas todavia."}

    subs = db.execute("SELECT * FROM push_subscriptions").fetchall()
    if not subs:
        return {"ok": False, "mensaje": "Nadie ha activado notificaciones push todavia."}

    if lotes:
        cuerpo = f"{len(lotes)} producto(s) en rojo o caducado(s). Revisa el dashboard."
    else:
        cuerpo = "Sin productos urgentes ni caducados ahorita."
    payload = json.dumps({"title": "PEPS ALARM", "body": cuerpo})

    enviados, caidos = 0, []
    for sub in subs:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        partes = urlsplit(sub["endpoint"])
        aud = f"{partes.scheme}://{partes.netloc}"
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": claim_email, "aud": aud},
            )
            enviados += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                caidos.append(sub["id"])
            # Si es otro tipo de error (red, endpoint invalido, etc.)
            # simplemente no contamos ese envio, pero no tumbamos el batch.
        except Exception:
            # Cualquier otra falla (ej. endpoint de prueba que no es una URL
            # real) tampoco debe tumbar el resto de los envios.
            pass
    for sub_id in caidos:
        db.execute("DELETE FROM push_subscriptions WHERE id = ?", (sub_id,))
    if caidos:
        db.commit()

    return {
        "ok": enviados > 0,
        "mensaje": f"Push enviado a {enviados} dispositivo(s). {len(caidos)} suscripcion(es) vencida(s) se limpiaron.",
    }
