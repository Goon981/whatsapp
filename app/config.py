"""Configuration centralisée. Les secrets proviennent de l'environnement (RM/NFR 11.2).

Aucune valeur sensible n'est codée en dur pour la production ; les valeurs par
défaut ne servent qu'au développement local.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

logger = logging.getLogger("smartshop")


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _is_production() -> bool:
    """Détecte un déploiement réel sans exiger une variable de plus.

    ``SMARTSHOP_ENV`` reste prioritaire, mais un hébergement Railway ou une URL
    publique en HTTPS suffisent : sans cela, une variable oubliée laissait le
    cookie de session sans l'attribut ``Secure`` en production.
    """
    declared = os.getenv("SMARTSHOP_ENV", "").strip().lower()
    if declared in {"production", "prod"}:
        return True
    if declared in {"development", "dev", "test"}:
        return False
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        return True
    return os.getenv("SMARTSHOP_PUBLIC_BASE_URL", "").strip().startswith("https://")


def _database_url() -> str:
    """URL de base de données, avec repli sur SQLite si elle est inexploitable.

    Une référence Railway non résolue (``${{Service.VAR}}`` laissé tel quel)
    faisait échouer la création du moteur au démarrage, donc tomber tout le
    site. Mieux vaut démarrer sur SQLite et le signaler via ``/health``.
    """
    raw = (os.getenv("SMARTSHOP_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    fallback = f"sqlite:///{PROJECT_DIR / 'smartshop.db'}"
    if not raw:
        return fallback

    url = raw.replace("postgres://", "postgresql://", 1)
    scheme = url.split("://", 1)[0] if "://" in url else ""
    if not scheme or not scheme.replace("+", "").isalnum():
        import logging

        logging.getLogger("smartshop").error(
            "URL de base de données inexploitable (référence non résolue ?) : "
            "repli sur SQLite, les données ne survivront pas au déploiement."
        )
        return fallback
    return url


_DEV_SECRET = "dev-insecure-secret-change-me-in-production"


def _secret_key() -> str:
    """Clé de signature des sessions, jamais une constante publique en production.

    Cette clé signe les jetons de session : quiconque la connaît peut forger un
    cookie de super-administrateur. La valeur de repli historique étant écrite
    dans le dépôt, elle n'est plus utilisée dès qu'un déploiement est détecté.
    On dérive alors une clé stable de l'URL de base de données (secrète et
    inchangée d'un déploiement à l'autre), à défaut une clé aléatoire — les
    sessions ne survivent alors pas au redémarrage, ce qui reste préférable à
    une signature falsifiable.
    """
    explicit = os.getenv("SMARTSHOP_SECRET_KEY", "").strip()
    if explicit and explicit != _DEV_SECRET:
        return explicit

    if not _is_production():
        return _DEV_SECRET

    seed = (os.getenv("SMARTSHOP_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if seed and "://" in seed:
        logger.warning(
            "SMARTSHOP_SECRET_KEY absent : clé de session dérivée de la base de "
            "données. Définissez SMARTSHOP_SECRET_KEY pour la rendre indépendante "
            "du mot de passe PostgreSQL."
        )
        return hashlib.sha256(f"baobay-session-key:{seed}".encode()).hexdigest()

    logger.error(
        "SMARTSHOP_SECRET_KEY absent et aucune base persistante : clé de session "
        "aléatoire, tout le monde sera déconnecté à chaque redémarrage."
    )
    return secrets.token_urlsafe(48)


def _shared_secret(name: str, dev_default: str) -> str:
    """Secret partagé (cron, webhook) : jamais de valeur par défaut en production."""
    value = os.getenv(name, "").strip()
    if value:
        return value
    if not _is_production():
        return dev_default
    # Valeur imprévisible : la route protégée refusera tout appel tant que le
    # secret n'est pas défini, plutôt que d'accepter la valeur du dépôt.
    logger.error("%s non défini : les appels correspondants seront tous refusés.", name)
    return secrets.token_urlsafe(48)


def _cors_origins() -> list[str]:
    """Origines autorisées, déduites du domaine public de l'application.

    ``SMARTSHOP_CORS_ORIGINS`` permet d'en ajouter (séparées par des virgules)
    pour un frontend hébergé ailleurs.
    """
    origins: list[str] = []
    for raw in os.getenv("SMARTSHOP_CORS_ORIGINS", "").split(","):
        cleaned = raw.strip().rstrip("/")
        if cleaned:
            origins.append(cleaned)

    public = os.getenv("SMARTSHOP_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public:
        origins.append(public)

    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if domain:
        origins.append(f"https://{domain}")

    if not _is_production():
        origins += ["http://localhost:8000", "http://127.0.0.1:8000"]

    # dict.fromkeys : dédoublonne en gardant l'ordre de priorité.
    return list(dict.fromkeys(origins))


class Settings:
    """Paramètres applicatifs lus depuis l'environnement."""

    APP_NAME: str = "BAOBAY"
    IS_PRODUCTION: bool = _is_production()
    ENV: str = os.getenv("SMARTSHOP_ENV", "production" if _is_production() else "development")
    DEBUG: bool = _get_bool("SMARTSHOP_DEBUG", not _is_production())

    # Secret utilisé pour signer les sessions et les jetons. DOIT être défini en prod.
    SECRET_KEY: str = _secret_key()

    # Base de données. SQLite par défaut ; PostgreSQL recommandé en production (NFR 12).
    # Accepte SMARTSHOP_DATABASE_URL (préféré) ou DATABASE_URL (nom fourni par
    # l'add-on PostgreSQL de Railway). "postgres://" est normalisé en
    # "postgresql://" car SQLAlchemy 2.x n'accepte plus l'ancien préfixe.
    DATABASE_URL: str = _database_url()

    # Durée de vie de la session commerçant / admin (secondes).
    SESSION_MAX_AGE: int = int(os.getenv("SMARTSHOP_SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))

    # Devise unique du MVP : franc CFA, montants stockés en entiers (RM-08).
    CURRENCY: str = "FCFA"

    # Secret partagé avec l'agrégateur de paiement pour signer les webhooks (RM-07).
    PAYMENT_WEBHOOK_SECRET: str = _shared_secret(
        "SMARTSHOP_PAYMENT_WEBHOOK_SECRET", "dev-payment-webhook-secret"
    )

    # Secret pour l'endpoint cron (suspension auto des abonnements impayés).
    CRON_SECRET: str = _shared_secret("SMARTSHOP_CRON_SECRET", "dev-cron-secret")

    # Bootstrap du super-administrateur après un déploiement neuf. L'endpoint
    # /api/setup/create-superadmin reste inerte tant que ce jeton est vide.
    # Documentation OpenAPI : fermée d'office en production (voir main.py).
    EXPOSE_DOCS: bool = _get_bool("SMARTSHOP_EXPOSE_DOCS", False)

    SETUP_TOKEN: str = os.getenv("SMARTSHOP_SETUP_TOKEN", "")
    ADMIN_EMAIL: str = os.getenv("SMARTSHOP_ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("SMARTSHOP_ADMIN_PASSWORD", "")

    # Base publique utilisée pour construire les liens de boutique et QR codes.
    PUBLIC_BASE_URL: str = os.getenv("SMARTSHOP_PUBLIC_BASE_URL", "http://localhost:8000")

    # Origines autorisées à appeler l'API avec les cookies de session. Une liste
    # explicite est indispensable : avec « * », Starlette renvoie l'origine de
    # l'appelant dès qu'un cookie est présent, ce qui laissait n'importe quel
    # site lire l'API au nom d'un commerçant connecté.
    CORS_ORIGINS: list[str] = _cors_origins()

    # Numéro WhatsApp du support (chiffres uniquement, format international).
    SUPPORT_WHATSAPP: str = os.getenv("SMARTSHOP_SUPPORT_WHATSAPP", "237600000000")

    # Envoi d'e-mails (réinitialisation de mot de passe). Sans SMTP_HOST, la
    # fonctionnalité reste accessible mais oriente vers le support WhatsApp.
    SMTP_HOST: str = os.getenv("SMARTSHOP_SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMARTSHOP_SMTP_PORT", "587") or 587)
    SMTP_USER: str = os.getenv("SMARTSHOP_SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMARTSHOP_SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMARTSHOP_SMTP_FROM", "")
    SMTP_TLS: bool = _get_bool("SMARTSHOP_SMTP_TLS", True)

    # Cookie sécurisé uniquement en HTTPS : activé d'office en production, où le
    # laisser à False exposait le jeton de session sur une connexion en clair.
    COOKIE_SECURE: bool = _get_bool("SMARTSHOP_COOKIE_SECURE", _is_production())

    # Campay Payment Gateway Configuration
    CAMPAY_APP_ID: str = os.getenv("CAMPAY_APP_ID", "")
    CAMPAY_API_USER: str = os.getenv("CAMPAY_API_USER", "")
    CAMPAY_API_PASSWORD: str = os.getenv("CAMPAY_API_PASSWORD", "")
    CAMPAY_WEBHOOK_KEY: str = os.getenv("CAMPAY_WEBHOOK_KEY", "")
    # Jeton permanent Campay : dispense de l'échange identifiants/jeton avant
    # chaque paiement. Prioritaire sur CAMPAY_API_USER / CAMPAY_API_PASSWORD.
    CAMPAY_PERMANENT_TOKEN: str = os.getenv("CAMPAY_PERMANENT_TOKEN", "")
    CAMPAY_MODE: str = os.getenv("CAMPAY_MODE", "sandbox")

    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    STATIC_DIR: Path = BASE_DIR / "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
