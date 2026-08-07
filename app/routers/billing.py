"""Gestion des abonnements et paiements."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import Shop, Subscription, SubscriptionPlan, SubscriptionStatus, ShopStatus, as_utc, utcnow
from app.deps import require_shop_access
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

SUPPORT_NUMBER = "690088572"
TRIAL_DAYS = 14

PLAN_PRICES = {
    "starter": 5000,      # 1 mois
    "business": 12000,    # 3 mois (4000/mois)
    "premium": 50000,     # 12 mois (4166/mois)
}


class PaymentRequest(BaseModel):
    """Demande de paiement."""
    plan: str          # "starter", "business", "premium"
    phone: str         # Numéro MTN/Orange


class PaymentConfirmation(BaseModel):
    """Confirmation de paiement reçu (webhook)."""
    shop_id: int
    plan: str
    amount_paid: int   # Montant reçu en FCFA
    reference: str     # Référence du paiement


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
                "price": 12000,
                "description": "3 mois (4000/mois) - Economie 3,000 FCFA"
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

    # Un abonnement payé prime sur l'essai : le webhook prolonge aussi
    # trial_expires_at pour garder l'accès ouvert, donc tester l'essai d'abord
    # annoncerait « en essai » à un client qui vient de payer.
    sub = shop.subscription
    if sub and sub.current_period_end and as_utc(sub.current_period_end) > now:
        days_remaining = (as_utc(sub.current_period_end) - now).days
        return {
            "status": "active",
            "plan": str(sub.plan),
            "days_remaining": days_remaining,
            "expires_at": str(sub.current_period_end),
            "message": f"Abonnement actif. Expire dans {days_remaining} jours"
        }

    # Sinon, l'essai en cours
    if shop.trial_expires_at:
        days_remaining = (as_utc(shop.trial_expires_at) - now).days
        if days_remaining > 0:
            return {
                "status": "trial",
                "days_remaining": days_remaining,
                "expires_at": shop.trial_expires_at,
                "message": f"Trial expire dans {days_remaining} jours",
                "payment_url": f"/app/payment?shop_id={shop_id}",
                "support": SUPPORT_NUMBER
            }

    if sub:
        return {
            "status": "expired",
            "message": "Abonnement expire. Paiement requis.",
            "payment_url": f"/app/payment?shop_id={shop_id}",
            "support": SUPPORT_NUMBER
        }

    if shop.trial_expires_at:
        return {
            "status": "trial_expired",
            "message": "Votre trial a expire. Paiement requis.",
            "payment_url": f"/app/payment?shop_id={shop_id}",
            "support": SUPPORT_NUMBER
        }

    return {
        "status": "no_subscription",
        "message": "Pas d'abonnement actif",
        "payment_url": f"/app/payment?shop_id={shop_id}",
        "support": SUPPORT_NUMBER
    }


@router.post("/check-expiry-and-notify")
async def check_expiry_and_notify(db: Session = Depends(get_db)):
    """Vérifier expiration et envoyer notifications WhatsApp.

    À appeler via cron job toutes les heures (en prod).
    """

    now = utcnow()
    shops = db.query(Shop).filter(Shop.is_deleted.is_(False)).all()

    notifications_sent = 0
    suspensions_done = 0

    for shop in shops:
        # Vérifier trial
        if shop.trial_expires_at:
            days_left = (as_utc(shop.trial_expires_at) - now).days

            # Notification 3 jours avant expiration du trial
            if days_left == 3:
                wa_url = f"https://wa.me/{shop.phone_number}?text=Votre%20trial%20BAOBAY%20expire%20dans%203%20jours.%20Passez%20à%20un%20abonnement%20payant%20pour%20continuer.%20https://shopcam237.com/app/payment"
                # En prod: appel HTTP à Twilio/gupshup pour envoyer le SMS/WhatsApp
                notifications_sent += 1

            # Bloquer la boutique si trial expiré et pas de paiement
            if days_left <= 0 and not shop.subscription:
                shop.status = ShopStatus.SUSPENDED
                db.add(shop)
                suspensions_done += 1

        # Vérifier subscription
        sub = shop.subscription
        if sub and sub.current_period_end:
            days_left = (as_utc(sub.current_period_end) - now).days

            # Notification 3 jours avant expiration de l'abonnement
            if days_left == 3:
                wa_url = f"https://wa.me/{shop.whatsapp_number}?text=Votre%20abonnement%20BAOBAY%20expire%20dans%203%20jours.%20Renouvelez%20pour%20rester%20actif.%20https://shopcam237.com/app/payment"
                notifications_sent += 1

            # Suspendre si subscription expirée
            if days_left <= 0:
                shop.status = ShopStatus.SUSPENDED
                db.add(shop)
                suspensions_done += 1

    db.commit()

    return {
        "notifications_sent": notifications_sent,
        "suspensions_done": suspensions_done,
        "timestamp": now
    }


@router.post("/validate-payment")
async def validate_payment(
    payment: PaymentConfirmation,
    db: Session = Depends(get_db)
):
    """Valider et confirmer le paiement AVANT de créer la subscription.

    Vérifie que le montant payé correspond EXACTEMENT au plan.
    Si le montant est insuffisant, rejette la transaction.
    """

    shop = db.query(Shop).filter(Shop.id == payment.shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    if payment.plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Plan invalide")

    # Vérifier que le montant est EXACTEMENT correct
    required_amount = PLAN_PRICES[payment.plan]
    if payment.amount_paid < required_amount:
        return {
            "success": False,
            "error": "MONTANT_INSUFFISANT",
            "message": f"Montant insuffisant: {payment.amount_paid} FCFA reçu, {required_amount} FCFA requis",
            "required_amount": required_amount,
            "received_amount": payment.amount_paid,
            "shortfall": required_amount - payment.amount_paid
        }

    if payment.amount_paid > required_amount:
        return {
            "success": False,
            "error": "MONTANT_EXCESSIF",
            "message": f"Montant excessif: {payment.amount_paid} FCFA reçu, {required_amount} FCFA attendu",
            "required_amount": required_amount,
            "received_amount": payment.amount_paid
        }

    # Montant exact ✓ → créer la subscription
    durations = {"starter": 1, "business": 3, "premium": 12}
    duration = durations[payment.plan]

    sub = shop.subscription or Subscription(shop_id=payment.shop_id)
    sub.plan = SubscriptionPlan[payment.plan.upper()]
    sub.current_period_end = utcnow() + timedelta(days=duration * 30)
    sub.status = SubscriptionStatus.ACTIVE

    db.add(sub)
    db.commit()

    return {
        "success": True,
        "message": f"Paiement accepté. Abonnement {payment.plan} activé pour {duration} mois",
        "reference": payment.reference,
        "expires_at": str(sub.current_period_end),
        "dashboard_url": f"/app?shop_id={payment.shop_id}"
    }


@router.post("/process-payment-sandbox")
async def process_payment_sandbox(
    shop_id: int,
    plan: str,
    db: Session = Depends(get_db)
):
    """Endpoint TEST SANDBOX pour traiter les paiements (sans API réelle).

    À utiliser UNIQUEMENT pour les tests. En production, utiliser MTN MoMo/Orange Money.
    """

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Plan invalide")

    # Montant exact requis
    required_amount = PLAN_PRICES[plan]
    durations = {"starter": 1, "business": 3, "premium": 12}
    duration = durations[plan]

    # Créer ou mettre à jour la subscription
    sub = shop.subscription or Subscription(shop_id=shop_id)
    sub.plan = SubscriptionPlan[plan.upper()] if plan.upper() in [p.name for p in SubscriptionPlan] else SubscriptionPlan.STARTER
    sub.current_period_end = utcnow() + timedelta(days=duration * 30)
    sub.status = SubscriptionStatus.ACTIVE

    db.add(sub)

    # Mettre aussi à jour trial_expires_at pour que le trial apparaisse comme payé
    shop.trial_expires_at = utcnow() + timedelta(days=duration * 30)
    db.add(shop)
    db.commit()

    return {
        "success": True,
        "plan": plan,
        "amount": required_amount,
        "duration_months": duration,
        "expires_at": str(sub.current_period_end),
        "message": f"SANDBOX: Paiement simulé - Abonnement {plan} activé pour {duration} mois"
    }


@router.post("/campay/initiate")
async def initiate_campay_payment(
    shop_id: int,
    plan: str,
    phone: str,
    network: str = "MTN",
    db: Session = Depends(get_db)
):
    """Initie un paiement via Campay (MTN, Orange, Airtel)."""

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")

    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Plan invalide")

    if network not in ["MTN", "ORANGE", "AIRTEL", "CARD"]:
        raise HTTPException(status_code=400, detail="Réseau non supporté")

    amount = PLAN_PRICES[plan]
    reference = f"SHOP{shop_id}_{int(utcnow().timestamp())}"

    clean_phone = phone.replace("+", "").lstrip("0")
    if not clean_phone.startswith("237"):
        clean_phone = "237" + clean_phone

    # En sandbox ou sans credentials, retourner une réponse de test
    if settings.CAMPAY_MODE == "sandbox" or not settings.CAMPAY_APP_ID:
        logger.info(f"Mode SANDBOX: Paiement {reference} pour {amount} FCFA sur {network}")
        return {
            "success": True,
            "reference": reference,
            "shop_id": shop_id,
            "plan": plan,
            "amount": amount,
            "phone": clean_phone,
            "network": network,
            "message": f"Paiement initié en mode test - {network}",
            "redirect_url": f"/app/payment?reference={reference}&provider=campay&mode=sandbox",
            "sandbox": True
        }

    # Mode production: appel à l'API Campay (utiliser requests ou urlib3 si httpx n'est pas disponible)
    if settings.CAMPAY_API_USER and settings.CAMPAY_API_PASSWORD:
        logger.info(f"Mode production: Initier paiement Campay pour {reference}")
        # TODO: Intégrer httpx ou requests pour l'appel API réel
        # Pour maintenant, retourner une réponse de test
        return {
            "success": True,
            "reference": reference,
            "shop_id": shop_id,
            "plan": plan,
            "amount": amount,
            "phone": clean_phone,
            "network": network,
            "message": "Paiement initié - Veuillez confirmer sur votre téléphone",
            "sandbox": False
        }

    # Fallback sandbox
    logger.info(f"Mode SANDBOX: Paiement {reference} pour {amount} FCFA sur {network}")
    return {
        "success": True,
        "reference": reference,
        "shop_id": shop_id,
        "plan": plan,
        "amount": amount,
        "phone": clean_phone,
        "network": network,
        "message": f"Paiement initié en mode test - {network}",
        "redirect_url": f"/app/payment?reference={reference}&provider=campay&mode=sandbox",
        "sandbox": True
    }


@router.post("/campay/callback")
async def campay_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook Campay pour confirmer les paiements.

    Reçoit les notifications de paiement depuis Campay et active l'abonnement.
    """

    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Invalid webhook payload: {e}")
        return {"error": "Invalid payload"}

    reference = data.get("reference")
    status = data.get("status", "").lower()
    amount = data.get("amount")
    phone = data.get("phone")

    logger.info(f"Campay webhook received: {reference} - {status}")

    if not reference:
        logger.error("No reference in webhook")
        return {"error": "No reference"}

    # Cas de succès
    if status in ["successful", "success"]:
        try:
            # Parser le shop_id depuis la référence (format: SHOP123_timestamp)
            parts = reference.split("_")
            shop_id = int(parts[0].replace("SHOP", ""))

            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if not shop:
                logger.error(f"Shop not found: {shop_id}")
                return {"error": "Shop not found"}

            # Mapper le montant au plan
            plans_map = {5000: "starter", 12000: "business", 50000: "premium"}
            plan = plans_map.get(amount, "starter")

            durations = {"starter": 1, "business": 3, "premium": 12}
            duration = durations[plan]

            # Créer ou mettre à jour l'abonnement
            sub = shop.subscription or Subscription(shop_id=shop_id)
            sub.plan = SubscriptionPlan[plan.upper()]
            sub.current_period_end = utcnow() + timedelta(days=duration * 30)
            sub.status = SubscriptionStatus.ACTIVE
            sub.amount = amount
            sub.last_payment_at = utcnow()

            db.add(sub)

            # Mettre à jour le shop
            shop.trial_expires_at = utcnow() + timedelta(days=duration * 30)
            db.add(shop)
            db.commit()

            logger.info(f"Subscription activated: shop={shop_id} plan={plan}")

            return {
                "success": True,
                "message": "Subscription créée",
                "shop_id": shop_id,
                "plan": plan,
                "reference": reference
            }

        except ValueError as e:
            logger.error(f"Invalid reference format: {reference} - {e}")
            return {"error": "Invalid reference format"}
        except Exception as e:
            logger.error(f"Error processing payment: {e}")
            db.rollback()
            return {"error": str(e)}

    # Cas d'échec
    elif status in ["failed", "error", "cancelled"]:
        logger.warning(f"Payment failed: {reference} - {status}")
        return {
            "success": False,
            "status": status,
            "reference": reference,
            "message": "Paiement échoué. Veuillez réessayer."
        }

    # Cas en attente
    elif status == "pending":
        logger.info(f"Payment pending: {reference}")
        return {
            "success": None,
            "status": "pending",
            "reference": reference,
            "message": "Paiement en attente de confirmation"
        }

    return {
        "status": status,
        "reference": reference,
        "message": f"Status inconnu: {status}"
    }
