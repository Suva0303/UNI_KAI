from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import TOKEN_EXPIRED, TOKEN_INVALID, verify_token

bearer = HTTPBearer(auto_error=False)


def _http_detail_from_token_error(exc: ValueError) -> str:
    code = str(exc.args[0]) if exc.args else ""
    if code == TOKEN_EXPIRED:
        return "Сессия истекла — войдите в панель снова."
    if code == TOKEN_INVALID:
        return "Токен недействителен — выполните вход заново (возможно, сменились настройки сервера)."
    return "Не удалось проверить токен — войдите снова."


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_http_detail_from_token_error(exc),
        ) from None

    if payload.get("sub") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return payload
