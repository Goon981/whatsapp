"""Petits utilitaires transverses."""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy.orm import Session

from . import models


def slugify(value: str) -> str:
    """Transforme un nom en slug URL court (ASCII, minuscules, tirets)."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "boutique"


def unique_shop_slug(db: Session, name: str) -> str:
    """Garantit l'unicité du slug de boutique (URL courte, §6.2)."""
    base = slugify(name)
    slug = base
    counter = 2
    while db.query(models.Shop).filter(models.Shop.slug == slug).first() is not None:
        slug = f"{base}-{counter}"
        counter += 1
    return slug
