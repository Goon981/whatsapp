"""Sécurité : hachage de mots de passe et jetons signés (stdlib uniquement).

- Mots de passe : PBKDF2-HMAC-SHA256 avec sel aléatoire (NFR 11.2).
- Jetons de session : payload JSON signé HMAC-SHA256 + expiration (pas de dépendance externe).
Aucun secret n'est journalisé ; le ``SECRET_KEY`` provient de l'environnement.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from .config import settings

_PBKDF2_ROUNDS = 210_000
_ALGO = "sha256"


# --------------------------------------------------------------------------- #
# Mots de passe
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Retourne ``pbkdf2_sha256$rounds$sel$hash`` (sel et hash en base64)."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds_s, salt_b64, hash_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(dk, expected)


# --------------------------------------------------------------------------- #
# Jetons signés (sessions / API)
# --------------------------------------------------------------------------- #
def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(payload: dict, max_age: int | None = None) -> str:
    """Crée un jeton ``base64(payload).base64(signature)`` avec expiration."""
    data = dict(payload)
    now = int(time.time())
    data.setdefault("iat", now)
    max_age = max_age if max_age is not None else settings.SESSION_MAX_AGE
    data["exp"] = now + max_age
    body = _b64url_encode(json.dumps(data, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}"


def verify_token(token: str) -> dict | None:
    """Vérifie signature et expiration ; retourne le payload ou ``None``."""
    try:
        body, sig_b64 = token.split(".")
    except (ValueError, AttributeError):
        return None
    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256
    ).digest()
    try:
        given_sig = _b64url_decode(sig_b64)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(expected_sig, given_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, TypeError):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload


# --------------------------------------------------------------------------- #
# Signatures de webhook de paiement (RM-07)
# --------------------------------------------------------------------------- #
def sign_payload(raw_body: bytes, secret: str | None = None) -> str:
    secret = secret or settings.PAYMENT_WEBHOOK_SECRET
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_signature(raw_body: bytes, signature: str, secret: str | None = None) -> bool:
    expected = sign_payload(raw_body, secret)
    return hmac.compare_digest(expected, signature or "")


def new_reference(prefix: str) -> str:
    """Référence courte unique (commande, paiement…)."""
    return f"{prefix}-{secrets.token_hex(4).upper()}"
