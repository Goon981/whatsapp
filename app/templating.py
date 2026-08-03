"""Configuration Jinja2 partagée par tous les routers HTML."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from .config import settings
from .services.pricing import format_fcfa

templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


def format_fcfa_short(amount: int) -> str:
    """Montant compact : 356 800 FCFA (séparateurs, sans décimales)."""
    return f"{int(amount):,}".replace(",", " ") + " FCFA"


# Filtres d'affichage des montants FCFA (entiers — RM-08).
templates.env.filters["fcfa"] = format_fcfa
templates.env.filters["fcfa_short"] = format_fcfa_short
templates.env.globals["app_name"] = settings.APP_NAME
