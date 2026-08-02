"""Dépendances FastAPI : authentification, session et isolation multi-tenant (RM-05).

Deux mécanismes de session, un seul format de jeton signé :
- Navigateur : cookie httponly ``smartshop_session``.
- Client API : en-tête ``Authorization: Bearer <token>``.

Toute ressource de boutique est résolue via ``require_shop_access`` qui vérifie que
l'utilisateur courant appartient bien à la boutique demandée.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db
from .security import verify_token

SESSION_COOKIE = "smartshop_session"


def _extract_token(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get(SESSION_COOKIE)


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> models.User | None:
    """Retourne l'utilisateur authentifié ou ``None`` (n'échoue pas)."""
    token = _extract_token(request, authorization)
    if not token:
        return None
    payload = verify_token(token)
    if not payload or "sub" not in payload:
        return None
    user = db.get(models.User, int(payload["sub"]))
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    user: models.User | None = Depends(get_current_user_optional),
) -> models.User:
    """Exige un utilisateur authentifié, sinon 401."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise."
        )
    return user


def require_superadmin(
    user: models.User = Depends(get_current_user),
) -> models.User:
    if user.role != models.UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Accès super-administrateur requis."
        )
    return user


def get_membership(
    db: Session, user: models.User, shop_id: int
) -> models.ShopMember | None:
    return (
        db.query(models.ShopMember)
        .filter(
            models.ShopMember.shop_id == shop_id,
            models.ShopMember.user_id == user.id,
        )
        .first()
    )


def require_shop_access(
    shop_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> tuple[models.Shop, models.ShopMember | None]:
    """Vérifie l'accès de l'utilisateur à la boutique (RM-05).

    Le super-administrateur accède en lecture pour support/sécurité (RM-06).
    Retourne ``(shop, membership)`` ; ``membership`` vaut ``None`` pour un superadmin.
    """
    shop = db.get(models.Shop, shop_id)
    if shop is None or shop.is_deleted:
        raise HTTPException(status_code=404, detail="Boutique introuvable.")

    if user.role == models.UserRole.SUPERADMIN:
        return shop, None

    membership = get_membership(db, user, shop_id)
    if membership is None and shop.owner_id != user.id:
        # Ne jamais révéler l'existence d'une boutique d'un autre tenant.
        raise HTTPException(status_code=404, detail="Boutique introuvable.")
    return shop, membership


def require_permission(area: str) -> Callable:
    """Fabrique une dépendance exigeant une permission précise sur la boutique.

    ``area`` ∈ {"orders", "catalog", "stock", "settings", "customers", "stats"}.
    Le propriétaire et le gestionnaire ont tous les droits ; le vendeur suit ses
    permissions fines (§6.1).
    """

    def _checker(
        access: tuple[models.Shop, models.ShopMember | None] = Depends(require_shop_access),
    ) -> tuple[models.Shop, models.ShopMember | None]:
        shop, membership = access
        # Superadmin (membership None via superadmin) : accès support.
        if membership is None:
            return access
        if membership.role in (models.UserRole.OWNER, models.UserRole.MANAGER):
            return access
        perms = membership.permissions or {}
        if not perms.get(area, False):
            raise HTTPException(
                status_code=403,
                detail=f"Permission « {area} » requise pour cette action.",
            )
        return access

    return _checker
