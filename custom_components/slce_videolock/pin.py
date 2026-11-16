"""Unlock PIN hashing helpers (never store plaintext)."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

UNLOCK_PIN_PATTERN = re.compile(r"^\d{4}$")
_PBKDF2_ITERATIONS = 120_000


def is_valid_unlock_pin(pin: str | None) -> bool:
    """Return True if pin is exactly four digits."""
    return bool(pin and UNLOCK_PIN_PATTERN.fullmatch(pin))


def hash_unlock_pin(pin: str, salt: str | None = None) -> tuple[str, str]:
    """Return (salt, hex_digest) for a 4-digit unlock PIN."""
    if not is_valid_unlock_pin(pin):
        raise ValueError("Unlock PIN must be exactly 4 digits")
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt_value.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    ).hex()
    return salt_value, digest


def verify_unlock_pin(pin: str | None, salt: str | None, digest: str | None) -> bool:
    """Constant-time compare of a candidate PIN against stored salt+hash."""
    if not pin or not salt or not digest:
        return False
    if not is_valid_unlock_pin(pin):
        return False
    try:
        _, candidate = hash_unlock_pin(pin, salt)
    except ValueError:
        return False
    return hmac.compare_digest(candidate, digest)
