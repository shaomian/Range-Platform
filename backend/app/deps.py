"""Shared FastAPI dependencies for authentication/authorization."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _resolve_user(token: str | None, db: Session) -> User:
    if not token:
        raise _CREDENTIALS_EXC
    payload = decode_access_token(token)
    if payload is None:
        raise _CREDENTIALS_EXC
    username = payload.get("sub")
    if not username:
        raise _CREDENTIALS_EXC
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    return _resolve_user(token, db)


def get_current_user_or_query(
    authorization: str | None = Header(None),
    token: str | None = Query(None),
    db: Session = Depends(get_db),
) -> User:
    bearer: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:]
    return _resolve_user(bearer or token, db)


def require_admin(current: User = Depends(get_current_user)) -> User:
    if current.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current
