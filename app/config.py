"""Configuration centralisée. Les secrets proviennent de l'environnement (RM/NFR 11.2).

Aucune valeur sensible n'est codée en dur pour la production ; les valeurs par
défaut ne servent qu'au développement local.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Paramètres applicatifs lus depuis l'environnement."""

    APP_NAME: str = "BAOBAY"
    ENV: str = os.getenv("SMARTSHOP_ENV", "development")
    DEBUG: bool = _get_bool("SMARTSHOP_DEBUG", True)

    # Secret utilisé pour signer les sessions et les jetons. DOIT être défini en prod.
    SECRET_KEY: str = os.getenv(
        "SMARTSHOP_SECRET_KEY", "dev-insecure-secret-change-me-in-production"
    )

    # Base de données. SQLite par défaut ; PostgreSQL recommandé en production (NFR 12).
    # Accepte SMARTSHOP_DATABASE_URL (préféré) ou DATABASE_URL (nom fourni par
    # l'add-on PostgreSQL de Railway). "postgres://" est normalisé en
    # "postgresql://" car SQLAlchemy 2.x n'accepte plus l'ancien préfixe.
    DATABASE_URL: str = (
        os.getenv("SMARTSHOP_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or f"sqlite:///{PROJECT_DIR / 'smartshop.db'}"
    ).replace("postgres://", "postgresql://", 1)

    # Durée de vie de la session commerçant / admin (secondes).
    SESSION_MAX_AGE: int = int(os.getenv("SMARTSHOP_SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))

    # Devise unique du MVP : franc CFA, montants stockés en entiers (RM-08).
    CURRENCY: str = "FCFA"

    # Secret partagé avec l'agrégateur de paiement pour signer les webhooks (RM-07).
    PAYMENT_WEBHOOK_SECRET: str = os.getenv(
        "SMARTSHOP_PAYMENT_WEBHOOK_SECRET", "dev-payment-webhook-secret"
    )

    # Secret pour l'endpoint cron (suspension auto des abonnements impayés).
    CRON_SECRET: str = os.getenv("SMARTSHOP_CRON_SECRET", "dev-cron-secret")

    # Bootstrap du super-administrateur après un déploiement neuf. L'endpoint
    # /api/setup/create-superadmin reste inerte tant que ce jeton est vide.
    SETUP_TOKEN: str = os.getenv("SMARTSHOP_SETUP_TOKEN", "")
    ADMIN_EMAIL: str = os.getenv("SMARTSHOP_ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("SMARTSHOP_ADMIN_PASSWORD", "")

    # Base publique utilisée pour construire les liens de boutique et QR codes.
    PUBLIC_BASE_URL: str = os.getenv("SMARTSHOP_PUBLIC_BASE_URL", "http://localhost:8000")

    # Numéro WhatsApp du support (chiffres uniquement, format international).
    SUPPORT_WHATSAPP: str = os.getenv("SMARTSHOP_SUPPORT_WHATSAPP", "237600000000")

    # Cookie sécurisé uniquement en HTTPS (mettre à True derrière TLS).
    COOKIE_SECURE: bool = _get_bool("SMARTSHOP_COOKIE_SECURE", False)

    # Campay Payment Gateway Configuration
    CAMPAY_APP_ID: str = os.getenv("CAMPAY_APP_ID", "")
    CAMPAY_API_USER: str = os.getenv("CAMPAY_API_USER", "")
    CAMPAY_API_PASSWORD: str = os.getenv("CAMPAY_API_PASSWORD", "")
    CAMPAY_WEBHOOK_KEY: str = os.getenv("CAMPAY_WEBHOOK_KEY", "")
    CAMPAY_MODE: str = os.getenv("CAMPAY_MODE", "sandbox")

    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    STATIC_DIR: Path = BASE_DIR / "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
