"""SQLite connection + schema bootstrap for PEPS ALARM.

Kept deliberately simple: one small internal tool, one file database,
no ORM. Explicit SQL is easy to read and easy to change.
"""
import base64
import secrets
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.security import hash_password

DB_PATH = Path(__file__).resolve().parent.parent / "peps_alarm.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('recibo', 'piso', 'admin')),
    estado TEXT NOT NULL DEFAULT 'activo',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    barcode TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    categoria TEXT
);

CREATE TABLE IF NOT EXISTS lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL REFERENCES products(barcode),
    cantidad INTEGER NOT NULL DEFAULT 1,
    fecha_caducidad TEXT NOT NULL,
    fecha_recibo TEXT NOT NULL DEFAULT (datetime('now')),
    usuario_id INTEGER REFERENCES users(id),
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'retirado', 'vendido')),
    retirado_at TEXT,
    retirado_por INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT UNIQUE NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    usuario_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

DEFAULT_SETTINGS = {
    "dias_amarillo": "15",
    "dias_rojo": "7",
    "teams_webhook_url": "",
}


def get_connection() -> sqlite3.Connection:
    # check_same_thread=False: algunos endpoints son async (ej. /push/subscribe)
    # y FastAPI los corre en el event loop, mientras que las dependencias
    # sync como esta se resuelven en un hilo de worker -- sin este flag
    # sqlite3 rechaza usar la conexion desde un hilo distinto al que la creo.
    # Seguimos siendo seguros porque cada request obtiene su propia conexion
    # nueva (nunca se comparte una conexion entre requests concurrentes).
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        # Migracion: bases de datos creadas antes de que existiera la
        # columna 'estado' no la tienen -- se la agregamos sin tocar nada.
        columnas = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
        if "estado" not in columnas:
            conn.execute("ALTER TABLE users ADD COLUMN estado TEXT NOT NULL DEFAULT 'activo'")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        _bootstrap_piso1(conn)
        _bootstrap_vapid_keys(conn)
        conn.commit()
    finally:
        conn.close()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _bootstrap_vapid_keys(conn: sqlite3.Connection) -> None:
    """Genera el par de llaves VAPID para Web Push la primera vez que la
    app arranca, si todavia no existen -- asi cualquier despliegue nuevo
    (local o en hosting) tiene notificaciones push funcionando sin pasos
    manuales extra. Si ya existen, no las toca (serian suscripciones de
    usuarios reales invalidadas si las regeneramos sin querer).
    """
    existe = conn.execute(
        "SELECT 1 FROM settings WHERE key = 'vapid_private_key'"
    ).fetchone()
    if existe:
        return

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # py_vapid.Vapid.from_string() espera el DER de la llave privada, en
    # base64 url-safe sin padding -- NO un PEM con encabezados.
    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    # La Push API del navegador (applicationServerKey) quiere el punto
    # publico sin comprimir: 0x04 + X (32 bytes) + Y (32 bytes).
    numbers = public_key.public_numbers()
    raw_point = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")

    for key, value in [
        ("vapid_private_key", _b64url(private_der)),
        ("vapid_public_key", _b64url(raw_point)),
        ("vapid_claim_email", "mailto:admin@example.com"),
    ]:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))


def _bootstrap_piso1(conn: sqlite3.Connection) -> None:
    """Crea el usuario compartido 'piso1' y su token de acceso por QR.

    Nadie teclea la contrasena de este usuario -- es aleatoria y nadie la
    conoce. El unico modo de entrar como 'piso1' es via /piso1?token=...
    con el token que vive en settings. Si el QR se pierde o se quiere
    revocar, el admin regenera el token desde /admin y el QR viejo deja
    de servir al instante.
    """
    existe_usuario = conn.execute(
        "SELECT 1 FROM users WHERE username = 'piso1'"
    ).fetchone()
    if not existe_usuario:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'piso')",
            ("piso1", hash_password(secrets.token_hex(16))),
        )
    existe_token = conn.execute(
        "SELECT 1 FROM settings WHERE key = 'piso1_token'"
    ).fetchone()
    if not existe_token:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('piso1_token', ?)",
            (secrets.token_urlsafe(16),),
        )


def get_db():
    """FastAPI dependency: yields a connection, closes it after the request."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
