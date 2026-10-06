"""PEPS ALARM - entry point."""
import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.routers import admin, auth, dashboard, push, recibo

app = FastAPI(title="PEPS ALARM")
# SESSION_SECRET fija (via variable de entorno) evita que todo el mundo
# se deslogee cada vez que el servidor se reinicia (ej. hosting gratis que
# duerme por inactividad). En local sin la variable, cae a una random --
# nadie depende de sesiones persistentes en desarrollo.
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(recibo.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(push.router)

ROLE_HOME = {"recibo": "/recibo", "piso": "/dashboard", "admin": "/admin"}


@app.on_event("startup")
def startup():
    init_db()


@app.get("/sw.js")
def service_worker():
    # Served from root (not /static) so its scope covers the whole app --
    # a service worker's scope defaults to the folder it's served from.
    return FileResponse("app/static/sw.js", media_type="application/javascript")


@app.get("/")
def root(request: Request):
    role = request.session.get("role")
    if role:
        return RedirectResponse(url=ROLE_HOME.get(role, "/login"))
    return RedirectResponse(url="/login")
