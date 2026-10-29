"""Password hashing, JWT tokens and a small login rate limiter."""

import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    expires = timedelta(minutes=settings.jwt_expire_minutes)
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + expires, "type": "access"}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, int(expires.total_seconds())


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


class LoginRateLimiter:
    """Sliding-window limiter keyed by email + client IP.

    In-process memory is enough for a single API instance. With several instances,
    move this to Redis so all instances share the counters.
    """

    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def is_blocked(self, key: str) -> bool:
        settings = get_settings()
        window = self._attempts[key]
        cutoff = time.monotonic() - settings.login_window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        return len(window) >= settings.login_max_attempts

    def record_failure(self, key: str) -> None:
        self._attempts[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


login_limiter = LoginRateLimiter()
