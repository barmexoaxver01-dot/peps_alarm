"""One-off: genera el par de llaves VAPID para Web Push y las guarda en
settings. Si ya existen, las regenera (util mientras ajustamos el formato).
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.database import get_connection, init_db


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


init_db()
conn = get_connection()

private_key = ec.generate_private_key(ec.SECP256R1())
public_key = private_key.public_key()

# py_vapid.Vapid.from_string() espera el DER de la llave privada, en
# base64 url-safe sin padding -- NO un PEM con encabezados.
private_der = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
private_b64url = b64url(private_der)

# La Push API del navegador (applicationServerKey) quiere el punto publico
# sin comprimir: 0x04 + X (32 bytes) + Y (32 bytes), en base64 url-safe.
numbers = public_key.public_numbers()
raw_point = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
public_b64url = b64url(raw_point)

for key, value in [
    ("vapid_private_key", private_b64url),
    ("vapid_public_key", public_b64url),
    ("vapid_claim_email", "mailto:admin@example.com"),
]:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
conn.commit()
conn.close()
print("Llaves VAPID regeneradas en el formato correcto.")
