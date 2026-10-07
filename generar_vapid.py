"""One-off manual: fuerza la regeneracion de las llaves VAPID.

Ya no hace falta correr esto a mano -- la app las genera sola en el primer
arranque (ver app/database.py::_bootstrap_vapid_keys). Este script solo
sirve si alguna vez quieres invalidar las suscripciones existentes y
empezar de cero con un par de llaves nuevo.
"""
from app.database import _bootstrap_vapid_keys, get_connection, init_db

init_db()
conn = get_connection()
conn.execute("DELETE FROM settings WHERE key IN "
             "('vapid_private_key', 'vapid_public_key', 'vapid_claim_email')")
_bootstrap_vapid_keys(conn)
conn.commit()
conn.close()
print("Llaves VAPID regeneradas -- las suscripciones viejas dejaran de servir.")
