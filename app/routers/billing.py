"""Gestion des abonnements et paiements."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, Subscription, SubscriptionPlan, SubscriptionStatus, utcnow
from app.deps import require_shop_access

router = APIRouter(prefix="/api/billing", tags=["billing"])

SUPPORT_NUMBER = "690088572"
TRIAL_DAYS = 14

PLAN_PRICES = {
    "starter": 5000,      # 1 mois
    "business": 15000,    # 3 mois
    "premium": 50000,     # 12 mois (annuel)
}


class SubscriptionPlan(BaseModel):
    """Plan d'abonnement disponible."""
    name: str           # "starter", "business", "premium"
    duration_months: int
    price: int         # FCFA
    description: str


class PaymentRequest(BaseModel):
    """Demande de paiement."""
    plan: str          # "starter", "business", "premium"
    phone: str         # Numéro MTN/Orange


@router.get("/plans")
async def get_plans():
    """Lister tous les plans disponibles."""
    return {
        "plans": [
            {
                "name": "starter",
                "duration_months": 1,
                "price": 5000,
                "description": "1 mois"
            },
            {
                "name": "business",
                "duration_months": 3,
                "price": 15000,
                "description": "3 mois (5000/mois)"
            },
            {
                "name": "premium",
                "duration_months": 12,
                "price": 50000,
                "description": "1 an (4166/mois) - Economie de 10,000 FCFA"
            }
        ],
        "support": SUPPORT_NUMBER,
        "trial_days": TRIAL_DAYS
    }


@router.get("/status/{shop_id}")
async def get_subscription_status(
    shop_id: int,
    db: Session = Depends(get_db)
):
    """Vérifier l'état de l'abonnement."""

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    now = utcnow()

    # Vérifier le trial
    if shop.trial_expires_at:
        days_remaining = (shop.trial_expires_at - now).days
        if days_remaining > 0:
            return {
                "status": "trial",
                "days_remaining": days_remaining,
                "expires_at": shop.trial_expires_at,
                "message": f"Trial expire dans {days_remaining} jours",
                "payment_url": f"/app/payment?shop_id={shop_id}",
                "support": SUPPORT_NUMBER
            }
        elif days_remaining <= 0:
            return {
                "status": "trial_expired",
                "message": "Votre trial a expire. Paiement requis.",
                "payment_url": f"/app/payment?shop_id={shop_id}",
                "support": SUPPORT_NUMBER
            }

    # Vérifier la subscription
    sub = shop.subscription
    if not sub:
        return {
            "status": "no_subscription",
            "message": "Pas d'abonnement actif",
            "payment_url": f"/app/payment?shop_id={shop_id}",
            "support": SUPPORT_NUMBER
        }

    if sub.expires_at and sub.expires_at > now:
        days_remaining = (sub.expires_at - now).days
        return {
            "status": "active",
            "plan": sub.plan,
            "days_remaining": days_remaining,
            "expires_at": sub.expires_at,
            "message": f"Abonnement actif. Expire dans {days_remaining} jours"
        }
    else:
        return {
            "status": "expired",
            "message": "Abonnement expire. Paiement requis.",
            "payment_url": f"/app/payment?shop_id={shop_id}",
            "support": SUPPORT_NUMBER
        }


@router.post("/create-subscription")
async def create_subscription(
    shop_id: int,
    plan: str,
    db: Session = Depends(get_db)
):
    """Créer une subscription après paiement.

    Simulation: en prod, appelé par le webhook de paiement (MTN/Orange).
    """

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Plan invalide")

    # Déterminer la durée en mois
    durations = {"starter": 1, "business": 3, "premium": 12}
    duration = durations[plan]

    # Créer/update la subscription
    sub = shop.subscription or Subscription(shop_id=shop_id)
    sub.plan = SubscriptionPlan[plan.upper()]
    sub.expires_at = utcnow() + timedelta(days=duration * 30)
    sub.status = SubscriptionStatus.ACTIVE

    db.add(sub)
    db.commit()

    return {
        "success": True,
        "message": f"Abonnement {plan} activate pour {duration} mois",
        "expires_at": sub.expires_at,
        "dashboard_url": f"/app?shop_id={shop_id}"
    }
