from datetime import timedelta

import bcrypt
import jwt

from .config import settings
from .models import ahora


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def crear_token(username: str) -> str:
    exp = ahora() + timedelta(minutes=settings.jwt_minutos)
    return jwt.encode({"sub": username, "exp": exp}, settings.jwt_secret, algorithm=settings.jwt_algoritmo)


def decodificar_token(token: str) -> str | None:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algoritmo])
        return data.get("sub")
    except jwt.PyJWTError:
        return None
