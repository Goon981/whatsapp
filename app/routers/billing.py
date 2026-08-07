"""Gestion des abonnements et paiements."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
import hmac
import httpx
import logging

from app.database import get_db
from app.models import Shop, Subscription, SubscriptionPlan, SubscriptionStatus, ShopStatus, as_utc, utcnow
from app.deps import require_shop_access, require_superadmin
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

SUPPORT_NUMBER = "690088572"
TRIAL_DAYS = 14

# Campay expose deux environnements distincts (identifiants non interchangeables).
CAMPAY_BASE_URLS = {
    "sandbox": "https://demo.campay.net/api",
    "production": "https://www.campay.net/api",
}
CAMPAY_TIMEOUT = 30.0

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
    access=Depends(require_shop_access),
    db: Session = Depends(get_db)
):
    """Vérifier l'état de l'abonnement (réservé aux membres de la boutique).

    Sans contrôle d'accès, parcourir les identifiants de boutique exposait la
    formule, l'échéance et l'état de paiement de tous les commerçants.
    """
    shop, _ = access

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
async def check_expiry_and_notify(request: Request, db: Session = Depends(get_db)):
    """Vérifier expiration et envoyer notifications WhatsApp.

    À appeler via cron job toutes les heures (en prod). La tâche suspend des
    boutiques : elle exige le secret ``SMARTSHOP_CRON_SECRET``.
    """
    provided = request.query_params.get("secret") or request.headers.get("X-Cron-Secret", "")
    if not hmac.compare_digest(provided, settings.CRON_SECRET):
        raise HTTPException(status_code=403, detail="Secret de tâche planifiée invalide")

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
    request: Request,
    db: Session = Depends(get_db)
):
    """Valider et confirmer le paiement AVANT de créer la subscription.

    Vérifie que le montant payé correspond EXACTEMENT au plan.
    Si le montant est insuffisant, rejette la transaction.

    Cette route active un abonnement : elle exige le même secret que le
    webhook, sans quoi n'importe qui pouvait s'en octroyer un.
    """
    _authorize_campay_webhook(request)

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
    superadmin=Depends(require_superadmin),
    db: Session = Depends(get_db)
):
    """Endpoint TEST SANDBOX pour traiter les paiements (sans API réelle).

    Active un abonnement sans paiement : réservé au super-administrateur et
    indisponible hors mode sandbox. Ouvert à tous, il offrait un abonnement
    gratuit à qui connaissait l'URL.
    """
    if settings.CAMPAY_MODE != "sandbox":
        raise HTTPException(status_code=404, detail="Not Found")

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


def _campay_configured() -> bool:
    """Campay n'est utilisable qu'avec un compte API complet."""
    return bool(settings.CAMPAY_API_USER and settings.CAMPAY_API_PASSWORD)


async def _campay_collect(reference: str, amount: int, phone: str, description: str) -> dict:
    """Demande un paiement à Campay et renvoie sa réponse.

    Lève ``httpx.HTTPError`` si Campay est injoignable et ``HTTPException``
    si Campay refuse la demande : l'échec ne doit jamais être présenté au
    commerçant comme un paiement initié.
    """
    base = CAMPAY_BASE_URLS.get(settings.CAMPAY_MODE, CAMPAY_BASE_URLS["sandbox"])

    async with httpx.AsyncClient(timeout=CAMPAY_TIMEOUT) as client:
        token_res = await client.post(
            f"{base}/token/",
            json={
                "username": settings.CAMPAY_API_USER,
                "password": settings.CAMPAY_API_PASSWORD,
            },
        )
        if token_res.status_code != 200:
            logger.error("Campay: authentification refusée (%s) %s", token_res.status_code, token_res.text)
            raise HTTPException(status_code=502, detail="Authentification Campay refusée")

        token = token_res.json().get("token")
        if not token:
            logger.error("Campay: réponse token inattendue %s", token_res.text)
            raise HTTPException(status_code=502, detail="Réponse Campay invalide")

        collect_res = await client.post(
            f"{base}/collect/",
            headers={"Authorization": f"Token {token}"},
            json={
                "amount": str(amount),
                "currency": "XAF",
                "from": phone,
                "description": description,
                "external_reference": reference,
            },
        )

    if collect_res.status_code not in (200, 201):
        logger.error("Campay: collecte refusée (%s) %s", collect_res.status_code, collect_res.text)
        raise HTTPException(status_code=502, detail=f"Campay a refusé le paiement : {collect_res.text}")

    return collect_res.json()


@router.post("/campay/initiate")
async def initiate_campay_payment(
    shop_id: int,
    plan: str,
    phone: str,
    network: str = "MTN",
    access=Depends(require_shop_access),
    db: Session = Depends(get_db)
):
    """Initie un paiement via Campay (MTN, Orange, Airtel).

    Réservé aux membres de la boutique : ouverte à tous, cette route permettait
    de déclencher une demande de paiement USSD sur n'importe quel numéro de
    téléphone, autant de fois que voulu, aux frais du compte Campay.
    """
    shop, _ = access

    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Plan invalide")

    if network not in ["MTN", "ORANGE", "AIRTEL", "CARD"]:
        raise HTTPException(status_code=400, detail="Réseau non supporté")

    amount = PLAN_PRICES[plan]
    # Le plan est encodé dans la référence : le webhook le relit directement
    # au lieu de le déduire du montant reçu.
    reference = f"SHOP{shop_id}_{plan}_{int(utcnow().timestamp())}"

    clean_phone = phone.replace("+", "").lstrip("0")
    if not clean_phone.startswith("237"):
        clean_phone = "237" + clean_phone

    # Sans compte API configuré, aucun appel réel n'est possible : on simule.
    if not _campay_configured():
        logger.info("Mode SIMULATION: paiement %s de %s FCFA sur %s", reference, amount, network)
        return {
            "success": True,
            "reference": reference,
            "shop_id": shop_id,
            "plan": plan,
            "amount": amount,
            "phone": clean_phone,
            "network": network,
            "message": f"Paiement simulé - {network} (Campay non configuré)",
            "redirect_url": f"/app/payment?reference={reference}&provider=campay&mode=simulation",
            "simulated": True,
        }

    logger.info("Campay (%s): initiation de %s pour %s FCFA", settings.CAMPAY_MODE, reference, amount)
    try:
        data = await _campay_collect(
            reference=reference,
            amount=amount,
            phone=clean_phone,
            description=f"Abonnement BAOBAY {plan} - {shop.name}",
        )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.error("Campay injoignable pour %s : %s", reference, exc)
        raise HTTPException(status_code=502, detail="Service de paiement injoignable. Réessayez.")

    return {
        "success": True,
        "reference": reference,
        "campay_reference": data.get("reference"),
        "ussd_code": data.get("ussd_code"),
        "operator": data.get("operator", network),
        "shop_id": shop_id,
        "plan": plan,
        "amount": amount,
        "phone": clean_phone,
        "network": network,
        "message": "Paiement initié - confirmez la demande sur votre téléphone",
        "simulated": False,
    }


def _authorize_campay_webhook(request: Request) -> None:
    """Vérifie le secret partagé avec Campay.

    Ce webhook active les abonnements : sans contrôle, n'importe qui pouvait
    forger un appel et s'octroyer un abonnement payant. Le secret est déclaré
    dans l'URL de rappel configurée chez Campay (``?key=…``) ou dans l'en-tête
    ``X-Campay-Key``. Tant qu'aucun secret n'est configuré, la route refuse
    d'agir plutôt que d'accepter n'importe quel appel.
    """
    expected = settings.CAMPAY_WEBHOOK_KEY
    if not expected:
        logger.error("CAMPAY_WEBHOOK_KEY non configuré : webhook refusé.")
        raise HTTPException(
            status_code=503,
            detail="Webhook non configuré : définissez CAMPAY_WEBHOOK_KEY.",
        )

    provided = request.query_params.get("key") or request.headers.get("X-Campay-Key", "")
    if not hmac.compare_digest(provided, expected):
        logger.warning("Webhook Campay rejeté : secret invalide.")
        raise HTTPException(status_code=403, detail="Signature de webhook invalide")


@router.post("/campay/callback")
async def campay_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook Campay pour confirmer les paiements.

    Reçoit les notifications de paiement depuis Campay et active l'abonnement.
    """
    _authorize_campay_webhook(request)

    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Invalid webhook payload: {e}")
        return {"error": "Invalid payload"}

    # Campay renvoie sa propre référence dans "reference" et la nôtre dans
    # "external_reference" : c'est celle-ci qui porte le shop_id et le plan.
    reference = data.get("external_reference") or data.get("reference")
    status = str(data.get("status", "")).lower()
    amount = data.get("amount")
    phone = data.get("phone")

    logger.info("Campay webhook reçu : %s - %s", reference, status)

    if not reference:
        logger.error("Webhook sans référence exploitable")
        return {"error": "No reference"}

    # Cas de succès
    if status in ["successful", "success"]:
        try:
            # Référence au format SHOP<id>_<plan>_<timestamp>. Les références
            # émises avant l'ajout du plan (SHOP<id>_<timestamp>) restent lisibles.
            parts = reference.split("_")
            shop_id = int(parts[0].replace("SHOP", ""))

            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if not shop:
                logger.error("Boutique introuvable : %s", shop_id)
                return {"error": "Shop not found"}

            plan = parts[1] if len(parts) > 2 and parts[1] in PLAN_PRICES else None
            if plan is None:
                # Repli : déduire le plan du montant. Campay peut l'envoyer en
                # texte ("12000" ou "12000.00"), d'où la conversion explicite —
                # sans elle la correspondance échouait et tout paiement était
                # traité comme le plan le moins cher.
                try:
                    paid = int(float(amount))
                except (TypeError, ValueError):
                    paid = 0
                plan = {v: k for k, v in PLAN_PRICES.items()}.get(paid, "starter")

            durations = {"starter": 1, "business": 3, "premium": 12}
            duration = durations[plan]

            # Créer ou mettre à jour l'abonnement
            sub = shop.subscription or Subscription(shop_id=shop_id)
            sub.plan = SubscriptionPlan[plan.upper()]
            sub.current_period_end = utcnow() + timedelta(days=duration * 30)
            sub.status = SubscriptionStatus.ACTIVE
            sub.amount = PLAN_PRICES[plan]
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
