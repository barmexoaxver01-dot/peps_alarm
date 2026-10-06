"""Auth dependencies: current-user lookup and role gates."""
import sqlite3

from fastapi import Depends, HTTPException, Request, status

from app.database import get_db


def get_current_user(request: Request, db: sqlite3.Connection = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row


def require_login(request: Request, db: sqlite3.Connection = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def require_role(*roles: str):
    def _check(user=Depends(require_login)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="No tienes permiso para esto, compa.")
        return user
    return _check
