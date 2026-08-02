"""Configuration Jinja2 partagée par tous les routers HTML."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from .config import settings
from .services.pricing import format_fcfa

templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

# Filtre d'affichage des montants FCFA (entiers — RM-08).
templates.env.filters["fcfa"] = format_fcfa
templates.env.globals["app_name"] = settings.APP_NAME
