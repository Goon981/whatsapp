"""Gestion des invitations et du trial (Option B du MVP)."""
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User, as_utc, utcnow
from app.deps import require_shop_access, require_superadmin
from app.security import create_token, hash_password, verify_token
from app.utils import unique_shop_slug

router = APIRouter(prefix="/api/invitations", tags=["invitations"])

TRIAL_DAYS = 15
MARKETING_WHATSAPP = "652222478"  # Numéro du marketeur
# Le lien d'invitation reste valable une semaine.
INVITE_MAX_AGE = 7 * 24 * 3600


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

    # Créer l'utilisateur. Le mot de passe est fixé à l'activation ; un hachage
    # d'une valeur aléatoire évite de laisser un champ vide en base.
    user = User(
        full_name=req.full_name,
        email=req.email,
        phone=req.phone,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        is_active=False  # Inactif jusqu'à l'activation
    )
    db.add(user)
    db.flush()

    # Créer la boutique avec trial. Le slug passe par l'utilitaire dédié :
    # deux boutiques homonymes produisaient sinon le même slug.
    trial_expires = utcnow() + timedelta(days=TRIAL_DAYS)
    shop = Shop(
        owner_id=user.id,
        name=req.shop_name,
        slug=unique_shop_slug(db, req.shop_name),
        trial_expires_at=trial_expires
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    activation_token = create_token({"invite": user.id}, max_age=INVITE_MAX_AGE)

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
        "activation_token": activation_token,
        "trial_expires_at": trial_expires,
        "message": f"Invitation créée. Trial: {TRIAL_DAYS} jours"
    }


class TrialActivation(BaseModel):
    """Activation d'un compte invité."""
    token: str
    password: str


@router.post("/activate-trial")
async def activate_trial(
    data: TrialActivation,
    db: Session = Depends(get_db)
):
    """Activer un compte invité et démarrer son essai.

    Le jeton signé remis à l'invitation est exigé : cette route n'était
    protégée par rien et fixait le mot de passe du propriétaire à partir d'un
    simple ``shop_id``, ce qui permettait de s'approprier toute boutique en
    attente d'activation.
    """
    payload = verify_token(data.token)
    if not payload or "invite" not in payload:
        raise HTTPException(status_code=403, detail="Lien d'invitation invalide ou expiré")

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères")

    user = db.get(User, int(payload["invite"]))
    if not user:
        raise HTTPException(status_code=404, detail="Invitation introuvable")
    if user.is_active:
        raise HTTPException(status_code=400, detail="Compte déjà activé")

    shop = db.query(Shop).filter(Shop.owner_id == user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    user.password_hash = hash_password(data.password)
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
    access=Depends(require_shop_access),
    db: Session = Depends(get_db)
):
    """Demander l'aide du marketeur.

    Réservé aux membres de la boutique : la route acceptait n'importe quel
    ``shop_id`` sans authentification.
    """
    shop, _ = access

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
    access=Depends(require_shop_access),
    db: Session = Depends(get_db)
):
    """Vérifier l'état du trial (réservé aux membres de la boutique)."""
    shop, _ = access

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
