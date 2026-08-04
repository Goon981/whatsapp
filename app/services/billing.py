"""Gestion des abonnements SaaS encaissés par la plateforme (§6.10, §7).

Modèle retenu : le super-administrateur marque un abonnement « payé » (ce qui
prolonge la période d'un mois) ; le système **suspend automatiquement** toute
boutique dont l'échéance est dépassée au-delà du délai de grâce, et la
**réactive automatiquement** dès qu'un paiement est enregistré.

Aucun montant n'est codé en dur côté client : les prix indicatifs ci-dessous
sont modifiables par l'administrateur (option « changer de formule »).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..security import new_reference

# Tarifs mensuels indicatifs (FCFA) et limites par formule (§6.10).
PLAN_PRICES: dict[models.SubscriptionPlan, int] = {
    models.SubscriptionPlan.TRIAL: 0,
    models.SubscriptionPlan.STARTER: 5000,
    models.SubscriptionPlan.BUSINESS: 15000,
    models.SubscriptionPlan.PREMIUM: 30000,
}
PLAN_LIMITS: dict[models.SubscriptionPlan, tuple[int, int]] = {
    # (produits max, commandes/mois max)
    models.SubscriptionPlan.TRIAL: (20, 50),
    models.SubscriptionPlan.STARTER: (50, 150),
    models.SubscriptionPlan.BUSINESS: (300, 1000),
    models.SubscriptionPlan.PREMIUM: (100000, 100000),
}
PLAN_LABELS = {
    "trial": "Essai", "starter": "Starter", "business": "Business", "premium": "Premium",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class BillingState:
    label: str          # « À jour », « Expire bientôt », « En retard », « Suspendu »
    css: str            # classe de badge
    days_left: int      # jours restants avant échéance (négatif si dépassé)
    is_overdue: bool
    is_suspended: bool


def state_of(shop: models.Shop, sub: models.Subscription | None, now: datetime | None = None) -> BillingState:
    """Calcule l'état de facturation lisible d'une boutique."""
    now = now or _now()
    if shop.status == models.ShopStatus.SUSPENDED:
        return BillingState("Suspendu", "red", -999, True, True)
    if sub is None or sub.current_period_end is None:
        return BillingState("À jour", "green", 999, False, False)
    end = _aware(sub.current_period_end)
    days_left = (end - now).days
    if end < now:
        return BillingState("En retard", "amber", days_left, True, False)
    if days_left <= 3:
        return BillingState("Expire bientôt", "amber", days_left, False, False)
    return BillingState("À jour", "green", days_left, False, False)


def mark_paid(
    db: Session,
    shop: models.Shop,
    *,
    months: int = 1,
    amount: int | None = None,
    method: str = "manual",
    actor: str | None = None,
) -> models.SubscriptionPayment:
    """Enregistre un paiement d'abonnement : prolonge la période et réactive la boutique."""
    sub = shop.subscription
    if sub is None:
        sub = models.Subscription(shop_id=shop.id, plan=models.SubscriptionPlan.STARTER)
        db.add(sub)
        db.flush()

    now = _now()
    # Repart de l'échéance courante si elle est dans le futur, sinon de maintenant.
    base = _aware(sub.current_period_end)
    period_start = base if (base and base > now) else now
    period_end = period_start + timedelta(days=30 * months)

    if amount is None:
        amount = sub.amount or PLAN_PRICES.get(sub.plan, 0)

    payment = models.SubscriptionPayment(
        shop_id=shop.id, subscription_id=sub.id, amount=amount, method=method,
        reference=new_reference("SUB"), period_start=period_start, period_end=period_end,
        recorded_by=actor,
    )
    db.add(payment)

    sub.current_period_end = period_end
    sub.status = models.SubscriptionStatus.ACTIVE
    sub.last_payment_at = now
    if not sub.amount:
        sub.amount = amount

    # Réactivation automatique si suspendue pour impayé.
    if sub.suspended_for_nonpayment and shop.status == models.ShopStatus.SUSPENDED:
        shop.status = models.ShopStatus.ACTIVE
        shop.suspended_reason = None
        sub.suspended_for_nonpayment = False

    db.commit()
    db.refresh(payment)
    return payment


def change_plan(db: Session, shop: models.Shop, plan: models.SubscriptionPlan) -> models.Subscription:
    sub = shop.subscription
    if sub is None:
        sub = models.Subscription(shop_id=shop.id)
        db.add(sub)
        db.flush()
    sub.plan = plan
    sub.amount = PLAN_PRICES.get(plan, sub.amount)
    sub.product_limit, sub.monthly_order_limit = PLAN_LIMITS.get(plan, (sub.product_limit, sub.monthly_order_limit))
    db.commit()
    db.refresh(sub)
    return sub


def set_amount(db: Session, shop: models.Shop, amount: int) -> None:
    if shop.subscription:
        shop.subscription.amount = max(0, amount)
        db.commit()


def enforce_all(db: Session, now: datetime | None = None) -> list[int]:
    """Suspend automatiquement les boutiques dont l'abonnement est impayé.

    Une boutique est suspendue si : abonnement non-essai, ``auto_suspend`` actif,
    échéance dépassée depuis plus que ``grace_days``. Retourne les ids suspendus.
    Idempotent : ne resuspend pas une boutique déjà suspendue.
    """
    now = now or _now()
    suspended: list[int] = []
    subs = (
        db.query(models.Subscription)
        .join(models.Shop, models.Shop.id == models.Subscription.shop_id)
        .filter(models.Shop.is_deleted.is_(False))
        .all()
    )
    for sub in subs:
        shop = db.get(models.Shop, sub.shop_id)
        if shop is None or shop.status == models.ShopStatus.SUSPENDED:
            continue
        if not sub.auto_suspend or sub.current_period_end is None:
            continue
        if sub.plan == models.SubscriptionPlan.TRIAL:
            # L'essai expiré est aussi suspendu (fin de période d'essai).
            pass
        deadline = _aware(sub.current_period_end) + timedelta(days=sub.grace_days or 0)
        if deadline < now:
            shop.status = models.ShopStatus.SUSPENDED
            shop.suspended_reason = "Abonnement impayé"
            sub.status = models.SubscriptionStatus.PAST_DUE
            sub.suspended_for_nonpayment = True
            db.add(models.AuditLog(
                actor="système", action="shop.auto_suspend",
                target=shop.name, shop_id=shop.id,
                data={"reason": "subscription_overdue"},
            ))
            suspended.append(shop.id)
    if suspended:
        db.commit()
    return suspended


def overview(db: Session, now: datetime | None = None) -> dict:
    """Indicateurs de facturation pour le tableau de bord admin."""
    now = now or _now()
    shops = db.query(models.Shop).filter(models.Shop.is_deleted.is_(False)).all()
    paying = 0
    overdue = 0
    suspended_np = 0
    mrr = 0
    for shop in shops:
        sub = shop.subscription
        st = state_of(shop, sub, now)
        if sub and sub.plan != models.SubscriptionPlan.TRIAL and not st.is_suspended and not st.is_overdue:
            paying += 1
            mrr += sub.amount or 0
        if st.is_overdue:
            overdue += 1
        if st.is_suspended:
            suspended_np += 1
    collected = (
        db.query(models.SubscriptionPayment)
        .with_entities(models.SubscriptionPayment.amount)
        .all()
    )
    total_collected = sum(a for (a,) in collected)
    return {
        "paying": paying,
        "overdue": overdue,
        "suspended": suspended_np,
        "mrr": mrr,
        "total_collected": int(total_collected),
        "total_shops": len(shops),
    }
