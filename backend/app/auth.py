from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.config import settings

TOKEN_EXPIRED = "TOKEN_EXPIRED"
TOKEN_INVALID = "TOKEN_INVALID"


def create_access_token(subject: str) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> dict:
    if not isinstance(token, str) or not token.strip():
        raise ValueError(TOKEN_INVALID) from None
    try:
        return jwt.decode(
            token.strip(),
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require_exp": True},
        )
    except ExpiredSignatureError as exc:
        raise ValueError(TOKEN_EXPIRED) from exc
    except JWTError as exc:
        raise ValueError(TOKEN_INVALID) from exc
