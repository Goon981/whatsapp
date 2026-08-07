"""Limitation de débit en mémoire pour les routes sensibles (NFR 11.2).

Les formulaires de connexion acceptaient un nombre illimité de tentatives : un
script pouvait essayer des milliers de mots de passe par minute sur un compte
connu. Le compteur vit dans le processus — suffisant pour un déploiement à
instance unique, et sans dépendance supplémentaire. Derrière plusieurs
instances, il faudra un stockage partagé (Redis).
"""
from __future__ import annotations

import threading
import time

# Fenêtre glissante : (identifiant) -> horodatages des tentatives retenues.
_ATTEMPTS: dict[str, list[float]] = {}
_LOCK = threading.Lock()

# Au-delà de ce volume de clés, on purge les fenêtres expirées pour éviter
# qu'une attaque distribuée ne fasse enfler le dictionnaire indéfiniment.
_GC_THRESHOLD = 5_000


def _prune(now: float, window: float) -> None:
    for key in [k for k, v in _ATTEMPTS.items() if not v or v[-1] <= now - window]:
        _ATTEMPTS.pop(key, None)


def hit(key: str, *, limit: int, window: int) -> tuple[bool, int]:
    """Enregistre une tentative. Retourne ``(autorisé, secondes_avant_reprise)``."""
    now = time.time()
    with _LOCK:
        if len(_ATTEMPTS) > _GC_THRESHOLD:
            _prune(now, window)

        recent = [t for t in _ATTEMPTS.get(key, []) if t > now - window]
        if len(recent) >= limit:
            _ATTEMPTS[key] = recent
            return False, max(1, int(recent[0] + window - now))

        recent.append(now)
        _ATTEMPTS[key] = recent
        return True, 0


def reset(key: str) -> None:
    """Efface le compteur : appelé après une authentification réussie."""
    with _LOCK:
        _ATTEMPTS.pop(key, None)


def client_ip(request) -> str:
    """IP de l'appelant en tenant compte du proxy de l'hébergeur.

    Railway place l'adresse réelle en tête de ``X-Forwarded-For`` ; sans cela
    toutes les requêtes partageraient l'IP du proxy et un seul attaquant
    bloquerait l'ensemble des utilisateurs.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "inconnu"
