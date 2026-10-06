"""Receiving area: scan barcode, confirm product, set fecha de caducidad."""
import sqlite3

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.deps import require_role
from app.ocr import extract_date_from_image

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/recibo")
def recibo_form(request: Request, user=Depends(require_role("recibo", "admin"))):
    return templates.TemplateResponse(
        request, "recibo.html", {"user": user, "mensaje": None}
    )


@router.post("/recibo/lookup", response_class=HTMLResponse)
def lookup_barcode(
    request: Request,
    barcode: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("recibo", "admin")),
):
    product = db.execute(
        "SELECT * FROM products WHERE barcode = ?", (barcode,)
    ).fetchone()
    return templates.TemplateResponse(
        request,
        "partials/producto_fields.html",
        {
            "barcode": barcode,
            "nombre": product["nombre"] if product else "",
            "es_nuevo": product is None,
        },
    )


@router.post("/recibo/ocr", response_class=HTMLResponse)
def ocr_fecha(
    request: Request,
    foto: UploadFile = File(...),
    user=Depends(require_role("recibo", "admin")),
):
    contenido = foto.file.read()
    resultado = extract_date_from_image(contenido)
    return templates.TemplateResponse(request, "partials/ocr_resultado.html", resultado)


@router.post("/recibo/submit", response_class=HTMLResponse)
def submit_lote(
    request: Request,
    barcode: str = Form(...),
    nombre: str = Form(...),
    categoria: str = Form(""),
    cantidad: int = Form(...),
    fecha_caducidad: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
    user=Depends(require_role("recibo", "admin")),
):
    db.execute(
        "INSERT INTO products (barcode, nombre, categoria) VALUES (?, ?, ?) "
        "ON CONFLICT(barcode) DO UPDATE SET nombre = excluded.nombre",
        (barcode, nombre, categoria or None),
    )
    db.execute(
        "INSERT INTO lotes (barcode, cantidad, fecha_caducidad, usuario_id) "
        "VALUES (?, ?, ?, ?)",
        (barcode, cantidad, fecha_caducidad, user["id"]),
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/recibo_confirmacion.html",
        {"nombre": nombre, "fecha_caducidad": fecha_caducidad},
    )
