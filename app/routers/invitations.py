"""Gestion des invitations et du trial (Option B du MVP)."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User, as_utc, utcnow
from app.deps import require_superadmin

router = APIRouter(prefix="/api/invitations", tags=["invitations"])

TRIAL_DAYS = 15
MARKETING_WHATSAPP = "652222478"  # Numéro du marketeur


class InvitationCreate(BaseModel):
    """Créer une invitation pour un nouveau commerçant."""
    full_name: str
    email: str
    phone: str
    shop_name: str


class MarketingHelpRequest(BaseModel):
    """Demander l'aide du marketeur."""
    subject: str
    message: str


@router.post("/create-invitation")
async def create_invitation(
    req: InvitationCreate,
    db: Session = Depends(get_db),
    superadmin: User = Depends(require_superadmin)
):
    """Créer une invitation pour un nouveau commerçant.

    Admin envoie l'invitation → Commerçant s'inscrit → Trial de 15 jours
    """

    # Vérifier que l'email n'existe pas
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    # Créer l'utilisateur
    user = User(
        full_name=req.full_name,
        email=req.email,
        phone=req.phone,
        password_hash="",  # À créer lors de l'activation
        is_active=False  # Inactif jusqu'à l'activation
    )
    db.add(user)
    db.flush()

    # Créer la boutique avec trial
    trial_expires = utcnow() + timedelta(days=TRIAL_DAYS)
    shop = Shop(
        owner_id=user.id,
        name=req.shop_name,
        slug=req.shop_name.lower().replace(" ", "-"),
        trial_expires_at=trial_expires
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    # TODO: Envoyer l'invitation par WhatsApp au commerçant
    # with open("templates/invitation_sms.txt") as f:
    #     template = f.read()
    # message = template.format(
    #     shop_name=shop.name,
    #     activation_link=f"https://shopcam237.com/app/activate?token={shop.id}",
    #     days=TRIAL_DAYS
    # )
    # send_whatsapp(phone=req.phone, message=message)

    return {
        "success": True,
        "shop_id": shop.id,
        "trial_expires_at": trial_expires,
        "message": f"Invitation créée. Trial: {TRIAL_DAYS} jours"
    }


@router.post("/activate-trial")
async def activate_trial(
    shop_id: int,
    password: str,
    db: Session = Depends(get_db)
):
    """Activer un compte avec trial de 15 jours."""

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    user = shop.owner
    if user.is_active:
        raise HTTPException(status_code=400, detail="Compte déjà activé")

    # Activer l'utilisateur
    from app.services.auth import hash_password
    user.password_hash = hash_password(password)
    user.is_active = True
    user.accepted_terms_at = utcnow()

    # Trial démarre maintenant
    shop.trial_expires_at = utcnow() + timedelta(days=TRIAL_DAYS)

    db.commit()

    return {
        "success": True,
        "message": f"Compte activé ! Trial de {TRIAL_DAYS} jours commencé",
        "trial_expires_at": shop.trial_expires_at
    }


@router.post("/marketing-help")
async def request_marketing_help(
    req: MarketingHelpRequest,
    shop_id: int,
    db: Session = Depends(get_db)
):
    """Demander l'aide du marketeur.

    Envoie un message WhatsApp au numéro du marketeur.
    """

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    # Construire le message pour le marketeur
    message = f"""
📱 **Demande marketing de {shop.name}**

Sujet: {req.subject}

Message: {req.message}

Téléphone: {shop.whatsapp_number or shop.contact_phone}

---
Répondez directement à ce numéro.
    """.strip()

    # TODO: Envoyer via WhatsApp API
    # send_whatsapp(phone=MARKETING_WHATSAPP, message=message)

    return {
        "success": True,
        "message": "Demande marketing envoyée au marketeur",
        "marketing_phone": MARKETING_WHATSAPP
    }


@router.get("/trial-status/{shop_id}")
async def get_trial_status(
    shop_id: int,
    db: Session = Depends(get_db)
):
    """Vérifier l'état du trial."""

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    if not shop.trial_expires_at:
        return {"status": "no_trial", "message": "Pas de trial actif"}

    now = utcnow()
    days_remaining = (as_utc(shop.trial_expires_at) - now).days

    if days_remaining < 0:
        return {
            "status": "expired",
            "message": "Trial expiré",
            "expired_at": shop.trial_expires_at,
            "action_required": "Upgrade vers un plan payant"
        }

    return {
        "status": "active",
        "days_remaining": days_remaining,
        "expires_at": shop.trial_expires_at,
        "warning": days_remaining < 3  # Alert si < 3 jours
    }
