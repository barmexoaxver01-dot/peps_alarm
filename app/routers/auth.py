"""Login / logout."""
import secrets
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.security import hash_password, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ROLE_HOME = {"recibo": "/recibo", "piso": "/dashboard", "admin": "/admin"}


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Usuario o contraseña incorrectos."},
            status_code=401,
        )
    if user["estado"] == "pendiente":
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Tu cuenta esta pendiente de aprobacion por un administrador."},
            status_code=403,
        )
    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["role"] = user["role"]
    return RedirectResponse(url=ROLE_HOME.get(user["role"], "/login"), status_code=303)


@router.get("/piso1")
def piso1_autologin(
    token: str,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
):
    """Acceso rapido para una TC/tablet compartida en piso: sin usuario ni
    contrasena, solo el token que trae el QR que genera el admin desde
    /admin. Pensado para un dispositivo fijo que usan varios asociados,
    no para una cuenta personal.
    """
    row = db.execute("SELECT value FROM settings WHERE key = 'piso1_token'").fetchone()
    if not row or not secrets.compare_digest(token, row["value"]):
        raise HTTPException(
            status_code=403,
            detail="Este QR ya no es valido (fue revocado o es incorrecto). Pide al admin uno nuevo.",
        )
    user = db.execute("SELECT * FROM users WHERE username = 'piso1'").fetchone()
    if not user:
        raise HTTPException(status_code=500, detail="El usuario piso1 no esta configurado todavia.")
    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["role"] = user["role"]
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/solicitar-acceso")
def solicitar_acceso_form(request: Request):
    return templates.TemplateResponse(
        request, "solicitar_acceso.html", {"error": None, "enviado": False}
    )


@router.post("/solicitar-acceso")
def solicitar_acceso_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    existente = db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    if existente:
        return templates.TemplateResponse(
            request,
            "solicitar_acceso.html",
            {"error": "Ese usuario ya existe o ya fue solicitado.", "enviado": False},
            status_code=400,
        )
    db.execute(
        "INSERT INTO users (username, password_hash, role, estado) VALUES (?, ?, ?, 'pendiente')",
        (username, hash_password(password), role),
    )
    db.commit()
    return templates.TemplateResponse(
        request, "solicitar_acceso.html", {"error": None, "enviado": True}
    )
