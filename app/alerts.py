"""Semaforo logic: how many days until a lote expires, and what color that is."""
import sqlite3
from datetime import date, datetime


def get_thresholds(db: sqlite3.Connection) -> tuple[int, int]:
    rows = db.execute(
        "SELECT key, value FROM settings WHERE key IN ('dias_amarillo', 'dias_rojo')"
    ).fetchall()
    values = {r["key"]: int(r["value"]) for r in rows}
    return values.get("dias_amarillo", 15), values.get("dias_rojo", 7)


def dias_restantes(fecha_caducidad: str) -> int:
    fecha = datetime.strptime(fecha_caducidad, "%Y-%m-%d").date()
    return (fecha - date.today()).days


def nivel_alerta(dias: int, dias_amarillo: int, dias_rojo: int) -> str:
    if dias < 0:
        return "caducado"
    if dias <= dias_rojo:
        return "rojo"
    if dias <= dias_amarillo:
        return "amarillo"
    return "verde"


NIVEL_STYLES = {
    "caducado": {"bg": "bg-black", "text": "text-white", "label": "CADUCADO"},
    "rojo": {"bg": "bg-red-500", "text": "text-white", "label": "Urgente"},
    "amarillo": {"bg": "bg-yellow-400", "text": "text-gray-900", "label": "Pronto"},
    "verde": {"bg": "bg-green-500", "text": "text-white", "label": "OK"},
}
