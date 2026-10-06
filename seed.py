"""Crea el primer usuario admin. Corre con: uv run python seed.py"""
from app.database import init_db, get_connection
from app.security import hash_password

DEFAULT_ADMIN = ("admin", "peps2024", "admin")


def main():
    init_db()
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (DEFAULT_ADMIN[0],)
        ).fetchone()
        if existing:
            print(f"Usuario '{DEFAULT_ADMIN[0]}' ya existe, no se toca nada.")
            return
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (DEFAULT_ADMIN[0], hash_password(DEFAULT_ADMIN[1]), DEFAULT_ADMIN[2]),
        )
        conn.commit()
        print(f"Usuario admin creado -> usuario: {DEFAULT_ADMIN[0]}  contraseña: {DEFAULT_ADMIN[1]}")
        print("¡Cámbiala en cuanto entres!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
