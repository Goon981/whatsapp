"""API d'authentification (§13) : inscription, connexion, session."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, ratelimit, schemas
from ..database import get_db
from ..deps import get_current_user
from ..models import utcnow
from ..ratelimit import client_ip
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Mêmes plafonds que le formulaire web : 8 tentatives par quart d'heure.
LOGIN_LIMIT = 8
LOGIN_WINDOW = 900


def _find_user(db: Session, identifier: str) -> models.User | None:
    identifier = identifier.strip()
    return (
        db.query(models.User)
        .filter((models.User.email == identifier) | (models.User.phone == identifier))
        .first()
    )


@router.post("/register", response_model=schemas.TokenOut, status_code=201)
def register(data: schemas.RegisterIn, db: Session = Depends(get_db)) -> schemas.TokenOut:
    if not data.email and not data.phone:
        raise HTTPException(422, "Un e-mail ou un téléphone est requis.")
    if not data.accept_terms:
        raise HTTPException(422, "Vous devez accepter les conditions d'utilisation.")
    if data.email and db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(409, "Cet e-mail est déjà utilisé.")
    if data.phone and db.query(models.User).filter(models.User.phone == data.phone).first():
        raise HTTPException(409, "Ce téléphone est déjà utilisé.")

    user = models.User(
        full_name=data.full_name,
        email=str(data.email) if data.email else None,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=models.UserRole.OWNER,
        accepted_terms_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token({"sub": str(user.id), "role": user.role.value})
    return schemas.TokenOut(access_token=token, user_id=user.id, role=user.role.value)


@router.post("/login", response_model=schemas.TokenOut)
def login(
    data: schemas.LoginIn, request: Request, db: Session = Depends(get_db)
) -> schemas.TokenOut:
    # Voir ``merchant.login_submit`` : plafonner par IP et par identifiant visé.
    throttle_keys = [
        f"api-login:ip:{client_ip(request)}",
        f"api-login:id:{data.identifier.strip().lower()}",
    ]
    for key in throttle_keys:
        allowed, retry_after = ratelimit.hit(key, limit=LOGIN_LIMIT, window=LOGIN_WINDOW)
        if not allowed:
            raise HTTPException(
                429,
                f"Trop de tentatives. Réessayez dans {retry_after} secondes.",
                headers={"Retry-After": str(retry_after)},
            )

    user = _find_user(db, data.identifier)
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Identifiants invalides.")
    if not user.is_active:
        raise HTTPException(403, "Compte désactivé.")

    for key in throttle_keys:
        ratelimit.reset(key)
    token = create_token({"sub": str(user.id), "role": user.role.value})
    return schemas.TokenOut(access_token=token, user_id=user.id, role=user.role.value)


@router.post("/refresh", response_model=schemas.TokenOut)
def refresh(user: models.User = Depends(get_current_user)) -> schemas.TokenOut:
    token = create_token({"sub": str(user.id), "role": user.role.value})
    return schemas.TokenOut(access_token=token, user_id=user.id, role=user.role.value)


@router.get("/me")
def me(user: models.User = Depends(get_current_user)) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.value,
    }
