"""Password verification, opaque sessions, CSRF, and fixed-window abuse controls."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass


SCRYPT_N = 2**14


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) > 1024:
        raise ValueError("Password is too long")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_hex, expected = encoded.split("$")
        if scheme != "scrypt" or len(expected) != 64:
            return False
        actual = hash_password(password, bytes.fromhex(salt_hex)).split("$")[-1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str, secret: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    remaining: int
    retry_after: int


class RateLimiter:
    """Bounded in-process limiter for the single-worker deployment contract."""

    def __init__(self, capacity: int, window_seconds: int = 60, max_keys: int = 10000):
        self.capacity = capacity
        self.window = window_seconds
        self.max_keys = max_keys
        self._buckets: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> RateDecision:
        current = time.monotonic() if now is None else now
        with self._lock:
            started, used = self._buckets.get(key, (current, 0))
            if current - started >= self.window:
                started, used = current, 0
            used += 1
            self._buckets[key] = (started, used)
            self._buckets.move_to_end(key)
            while len(self._buckets) > self.max_keys:
                self._buckets.popitem(last=False)
            return RateDecision(
                allowed=used <= self.capacity,
                remaining=max(0, self.capacity - used),
                retry_after=max(1, int(self.window - (current - started)) + 1),
            )

    def clear(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)
