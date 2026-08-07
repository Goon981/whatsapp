"""Configuration Jinja2 partagée par tous les routers HTML."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .config import settings
from .services.icons import icon
from .services.pricing import format_fcfa
from .services.theme import theme_style

templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


def format_fcfa_short(amount: int) -> str:
    """Montant compact : 356 800 FCFA (séparateurs, sans décimales)."""
    return f"{int(amount):,}".replace(",", " ") + " FCFA"


@lru_cache(maxsize=64)
def _asset_digest(path: str) -> str:
    """Empreinte courte du contenu d'un fichier de ``/static``."""
    target = Path(settings.STATIC_DIR) / path.lstrip("/")
    try:
        return hashlib.sha256(target.read_bytes()).hexdigest()[:10]
    except OSError:
        # Fichier absent : la version applicative suffit à distinguer les
        # déploiements, mieux vaut servir la page que la faire échouer.
        return "0"


def asset(path: str) -> str:
    """URL d'un fichier statique suffixée par l'empreinte de son contenu.

    Les réponses HTML sont marquées ``no-store``, mais pas les fichiers de
    ``/static`` : sans ce suffixe, les navigateurs conservaient l'ancienne
    feuille de style après un déploiement et affichaient la nouvelle page avec
    le style précédent. L'empreinte ne change que si le fichier change, ce qui
    préserve le cache entre deux déploiements sans modification.
    """
    clean = path.lstrip("/")
    return f"/static/{clean}?v={_asset_digest(clean)}"


# Filtres d'affichage des montants FCFA (entiers — RM-08).
templates.env.filters["fcfa"] = format_fcfa
templates.env.filters["fcfa_short"] = format_fcfa_short
templates.env.globals["app_name"] = settings.APP_NAME
# Palette de boutique : dérive toutes les nuances de la couleur choisie.
templates.env.globals["theme_style"] = theme_style
# URL versionnée des fichiers statiques (voir ``asset``).
templates.env.globals["asset"] = asset
# Icônes vectorielles en ligne, en remplacement des emojis (voir services/icons.py).
templates.env.globals["icon"] = icon
