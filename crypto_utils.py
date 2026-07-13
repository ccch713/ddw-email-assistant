"""AES-256 encryption helpers for credential storage.

Key is read from env var DDW_EMAIL_SECRET_KEY.
Falls back to a dev-mode key (NOT for production).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os


def _get_key() -> bytes:
    """Derive a 32-byte key from the env var."""
    raw = os.environ.get("DDW_EMAIL_SECRET_KEY", "ddw-dev-only-not-for-production")
    return hashlib.sha256(raw.encode()).digest()


def encrypt_credentials(data: dict) -> str:
    """Encrypt a dict → base64 string (AES-256 via Fernet)."""
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(_get_key())
    f = Fernet(key)
    token = f.encrypt(json.dumps(data, ensure_ascii=False).encode())
    return token.decode()


def decrypt_credentials(token: str) -> dict:
    """Decrypt base64 string → dict."""
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(_get_key())
    f = Fernet(key)
    plaintext = f.decrypt(token.encode())
    return json.loads(plaintext.decode())
