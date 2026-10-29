from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import settings

_ph = PasswordHasher()


def hash_password(p: str) -> str:
    return _ph.hash(p)


def verify_password(p: str, h: str) -> bool:
    try:
        return _ph.verify(h, p)
    except (VerifyMismatchError, Exception):
        return False


def create_token(user_id: int, rol: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_minutes)
    return jwt.encode({"sub": str(user_id), "rol": rol, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def decode_token(t: str) -> dict:
    return jwt.decode(t, settings.jwt_secret, algorithms=["HS256"])
