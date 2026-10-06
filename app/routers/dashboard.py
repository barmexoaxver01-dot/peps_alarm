"""Piso de venta: ver alarmas de caducidad y marcar productos retirados."""
import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.alerts import NIVEL_STYLES, dias_restantes, get_thresholds, nivel_alerta
from app.database import get_db
from app.deps import require_role
from app.notifications import enviar_push_a_todos, enviar_resumen_teams

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

NIVEL_ORDEN = {"caducado": 0, "rojo": 1, "amarillo": 2, "verde": 3}


def _lotes_activos_con_alerta(db: sqlite3.Connection) -> list[dict]:
    dias_amarillo, dias_rojo = get_thresholds(db)
    rows = db.execute(
        """
        SELECT lotes.id, lotes.barcode, lotes.cantidad, lotes.fecha_caducidad,
               products.nombre, products.categoria
        FROM lotes
        JOIN products ON products.barcode = lotes.barcode
        WHERE lotes.estado = 'activo'
        """
    ).fetchall()

    lotes = []
    for row in rows:
        dias = dias_restantes(row["fecha_caducidad"])
        nivel = nivel_alerta(dias, dias_amarillo, dias_rojo)
        lotes.append(
            {
                **dict(row),
                "dias_restantes": dias,
                "nivel": nivel,
                "estilo": NIVEL_STYLES[nivel],
            }
        )
    lotes.sort(key=lambda lote: (NIVEL_ORDEN[lote["nivel"]], lote["dias_restantes"]))
    return lotes


@router.get("/dashboard")
def dashboard(request: Request, db: sqlite3.Connection = Depends(get_db), user=Depends(require_role("piso", "admin"))):
    lotes = _lotes_activos_con_alerta(db)
    resumen = {nivel: sum(1 for l in lotes if l["nivel"] == nivel) for nivel in NIVEL_STYLES}
    return templates.TemplateResponse(
        request, "dashboard.html", {"user": user, "lotes": lotes, "resumen": resumen}
    )


@router.post("/dashboard/retirar/{lote_id}", response_class=HTMLResponse)
def retirar_lote(
    lote_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("piso", "admin")),
):
    db.execute(
        "UPDATE lotes SET estado = 'retirado', retirado_at = datetime('now'), retirado_por = ? "
        "WHERE id = ?",
        (user["id"], lote_id),
    )
    db.commit()
    return HTMLResponse("")  # HTMX swap: row just disappears


@router.post("/dashboard/notificar", response_class=HTMLResponse)
def notificar_teams(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("piso", "admin")),
):
    webhook_url = db.execute(
        "SELECT value FROM settings WHERE key = 'teams_webhook_url'"
    ).fetchone()["value"]
    lotes = _lotes_activos_con_alerta(db)
    urgentes = [lote for lote in lotes if lote["nivel"] in ("rojo", "caducado")]
    resultado = enviar_resumen_teams(webhook_url, urgentes)
    return templates.TemplateResponse(request, "partials/notificacion_resultado.html", resultado)


@router.post("/dashboard/notificar-push", response_class=HTMLResponse)
def notificar_push(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("piso", "admin")),
):
    lotes = _lotes_activos_con_alerta(db)
    urgentes = [lote for lote in lotes if lote["nivel"] in ("rojo", "caducado")]
    resultado = enviar_push_a_todos(db, urgentes)
    return templates.TemplateResponse(request, "partials/notificacion_resultado.html", resultado)
