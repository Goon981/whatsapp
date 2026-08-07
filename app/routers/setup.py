"""Bootstrap du super-administrateur sur un déploiement neuf.

L'endpoint est volontairement inerte tant que ``SMARTSHOP_SETUP_TOKEN`` n'est
pas défini : sans jeton, il répond 404 et ne crée rien. Les identifiants ne
sont jamais codés en dur, ils proviennent de l'environnement.
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, UserRole, utcnow
from ..security import hash_password

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.post("/create-superadmin")
async def create_superadmin(
    token: str = Query(..., description="Valeur de SMARTSHOP_SETUP_TOKEN"),
    db: Session = Depends(get_db),
):
    """Crée le super-administrateur défini par les variables d'environnement.

    Idempotent : si un super-administrateur existe déjà, rien n'est modifié.
    """
    if not settings.SETUP_TOKEN:
        # Endpoint désactivé : ne pas révéler son existence.
        raise HTTPException(status_code=404, detail="Not Found")

    # Comparaison à temps constant pour ne pas fuiter le jeton octet par octet.
    if not hmac.compare_digest(token, settings.SETUP_TOKEN):
        raise HTTPException(status_code=403, detail="Jeton de setup invalide")

    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=400,
            detail=(
                "Définissez SMARTSHOP_ADMIN_EMAIL et SMARTSHOP_ADMIN_PASSWORD "
                "avant d'appeler cet endpoint."
            ),
        )

    existing = db.query(User).filter(User.role == UserRole.SUPERADMIN).first()
    if existing:
        return {
            "success": False,
            "message": "Un super-administrateur existe déjà.",
            "email": existing.email,
        }

    admin = User(
        full_name="BAOBAY Admin",
        email=settings.ADMIN_EMAIL,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        role=UserRole.SUPERADMIN,
        is_active=True,
        phone_verified=True,
        accepted_terms_at=utcnow(),
    )
    db.add(admin)
    db.commit()

    return {
        "success": True,
        "message": "Super-administrateur créé. Connectez-vous sur /admin.",
        "email": settings.ADMIN_EMAIL,
    }
