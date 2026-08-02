"""Logique métier des commandes et paiements côté serveur.

Regroupe les règles sensibles :
- Création de commande atomique, enregistrée une seule fois (§15 « Commande »).
- Réservation de stock à la confirmation OU au paiement selon le réglage boutique (RM-04).
- Transitions de statut contrôlées ; une commande payée n'est pas supprimable (RM-03).
- Traitement de webhook idempotent (RM-07).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..security import new_reference
from . import payments as payments_service
from .pricing import PricedCart, PricingError

# Transitions autorisées entre statuts de commande.
_ALLOWED_TRANSITIONS: dict[models.OrderStatus, set[models.OrderStatus]] = {
    models.OrderStatus.NEW: {models.OrderStatus.CONFIRMED, models.OrderStatus.CANCELLED},
    models.OrderStatus.CONFIRMED: {models.OrderStatus.PREPARING, models.OrderStatus.CANCELLED},
    models.OrderStatus.PREPARING: {models.OrderStatus.READY, models.OrderStatus.CANCELLED},
    models.OrderStatus.READY: {models.OrderStatus.DELIVERING, models.OrderStatus.CANCELLED},
    models.OrderStatus.DELIVERING: {models.OrderStatus.DELIVERED, models.OrderStatus.CANCELLED},
    models.OrderStatus.DELIVERED: {models.OrderStatus.REFUNDED},
    models.OrderStatus.CANCELLED: set(),
    models.OrderStatus.REFUNDED: set(),
}


class OrderError(Exception):
    """Erreur métier liée aux commandes."""


def _upsert_customer(
    db: Session, shop_id: int, name: str, phone: str, *, marketing_consent: bool = False
) -> models.Customer:
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.shop_id == shop_id, models.Customer.phone == phone)
        .first()
    )
    if customer is None:
        customer = models.Customer(
            shop_id=shop_id, full_name=name, phone=phone, marketing_consent=marketing_consent
        )
        db.add(customer)
        db.flush()
    else:
        if name and customer.full_name != name:
            customer.full_name = name
    if customer.is_blocked:
        raise OrderError("Ce client est bloqué et ne peut pas commander.")
    return customer


def create_order(
    db: Session,
    shop: models.Shop,
    priced: PricedCart,
    *,
    customer_name: str,
    customer_phone: str,
    payment_method: models.PaymentMethod,
    delivery_city: str | None = None,
    delivery_district: str | None = None,
    delivery_details: str | None = None,
    delivery_zone: models.DeliveryZone | None = None,
    is_pickup: bool = False,
    customer_note: str | None = None,
    marketing_consent: bool = False,
) -> models.Order:
    """Crée une commande à partir d'un panier déjà tarifé côté serveur.

    Vérifie le montant minimum et le mode de paiement autorisé par la boutique.
    """
    if shop.status != models.ShopStatus.ACTIVE:
        raise OrderError("Cette boutique n'accepte pas de commande actuellement.")
    if not priced.lines:
        raise PricingError("Le panier est vide.")
    if priced.subtotal < shop.min_order_amount:
        raise OrderError(
            f"Le minimum de commande est de {shop.min_order_amount} FCFA."
        )
    _assert_method_allowed(shop, payment_method)

    customer = _upsert_customer(
        db, shop.id, customer_name, customer_phone, marketing_consent=marketing_consent
    )

    order = models.Order(
        shop_id=shop.id,
        reference=new_reference("CMD"),
        customer_id=customer.id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_city=delivery_city,
        delivery_district=delivery_district,
        delivery_details=delivery_details,
        delivery_zone_id=delivery_zone.id if delivery_zone else None,
        is_pickup=is_pickup,
        subtotal=priced.subtotal,
        delivery_fee=priced.delivery_fee,
        discount=priced.discount,
        total=priced.total,
        payment_method=payment_method,
        status=models.OrderStatus.NEW,
        customer_note=customer_note,
    )
    db.add(order)
    db.flush()

    for line in priced.lines:
        db.add(
            models.OrderItem(
                shop_id=shop.id,
                order_id=order.id,
                product_id=line.product.id,
                variant_id=line.variant.id if line.variant else None,
                product_name=line.product.name,
                variant_name=line.variant.name if line.variant else None,
                unit_price=line.unit_price,
                quantity=line.quantity,
                line_total=line.line_total,
            )
        )

    _add_history(db, order, models.OrderStatus.NEW, note="Commande créée", actor="client")
    db.commit()
    db.refresh(order)
    return order


def _assert_method_allowed(shop: models.Shop, method: models.PaymentMethod) -> None:
    allowed = {
        models.PaymentMethod.CASH_ON_DELIVERY: shop.accept_cash_on_delivery,
        models.PaymentMethod.MTN_MOMO: shop.accept_mtn_momo,
        models.PaymentMethod.ORANGE_MONEY: shop.accept_orange_money,
    }
    if not allowed.get(method, False):
        raise OrderError("Ce mode de paiement n'est pas accepté par la boutique.")


def _add_history(
    db: Session,
    order: models.Order,
    status: models.OrderStatus,
    *,
    note: str | None = None,
    actor: str | None = None,
) -> None:
    db.add(
        models.OrderStatusHistory(
            order_id=order.id, status=status, note=note, changed_by=actor
        )
    )


def _reserve_stock(db: Session, order: models.Order) -> None:
    """Décrémente le stock des variantes/produits de la commande (RM-04)."""
    if order.stock_reserved:
        return
    for item in order.items:
        if item.variant_id:
            variant = db.get(models.ProductVariant, item.variant_id)
            if variant is not None:
                variant.stock = max(0, variant.stock - item.quantity)
        elif item.product_id:
            product = db.get(models.Product, item.product_id)
            if product is not None:
                product.stock = max(0, product.stock - item.quantity)
                if product.stock == 0 and product.status == models.ProductStatus.AVAILABLE:
                    product.status = models.ProductStatus.OUT_OF_STOCK
    order.stock_reserved = True


def _release_stock(db: Session, order: models.Order) -> None:
    """Restitue le stock si une commande réservée est annulée."""
    if not order.stock_reserved:
        return
    for item in order.items:
        if item.variant_id:
            variant = db.get(models.ProductVariant, item.variant_id)
            if variant is not None:
                variant.stock += item.quantity
        elif item.product_id:
            product = db.get(models.Product, item.product_id)
            if product is not None:
                product.stock += item.quantity
                if product.status == models.ProductStatus.OUT_OF_STOCK and product.stock > 0:
                    product.status = models.ProductStatus.AVAILABLE
    order.stock_reserved = False


def change_status(
    db: Session,
    order: models.Order,
    new_status: models.OrderStatus,
    *,
    actor: str | None = None,
    note: str | None = None,
) -> models.Order:
    """Applique une transition de statut valide et gère le stock associé."""
    if new_status == order.status:
        return order
    allowed = _ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise OrderError(
            f"Transition interdite : {order.status.value} → {new_status.value}."
        )

    shop = db.get(models.Shop, order.shop_id)
    # Réservation à la confirmation si la boutique le demande (RM-04).
    if new_status == models.OrderStatus.CONFIRMED and shop and shop.reserve_stock_on_confirm:
        _reserve_stock(db, order)
    if new_status == models.OrderStatus.CANCELLED:
        _release_stock(db, order)

    order.status = new_status
    _add_history(db, order, new_status, note=note, actor=actor)
    db.commit()
    db.refresh(order)
    return order


def can_delete(order: models.Order) -> bool:
    """RM-03 : une commande payée ne peut jamais être supprimée."""
    return not order.is_paid


# --------------------------------------------------------------------------- #
# Paiements
# --------------------------------------------------------------------------- #
def initiate_payment(
    db: Session, order: models.Order, method: models.PaymentMethod
) -> models.Payment:
    """Initialise une transaction Mobile Money via l'agrégateur (statut en attente)."""
    if method == models.PaymentMethod.CASH_ON_DELIVERY:
        raise OrderError("Le paiement à la livraison ne nécessite pas d'initialisation.")
    provider = payments_service.get_provider(payments_service.method_to_provider(method))
    result = provider.initialize(order, method)
    payment = models.Payment(
        shop_id=order.shop_id,
        order_id=order.id,
        provider=provider.name,
        method=method,
        reference=result.reference,
        provider_reference=result.provider_reference,
        amount=order.total,
        status=result.status,
        events=[{"type": "initiated", "at": _now_iso()}],
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def apply_payment_event(
    db: Session,
    event_id: str,
    provider: str,
    payment_reference: str,
    new_status: models.PaymentStatus,
    payload: dict,
) -> models.Payment:
    """Applique un évènement de webhook de façon IDEMPOTENTE (RM-07).

    Le même ``event_id`` ne peut jamais être traité deux fois. Lève ``OrderError``
    si l'évènement est un doublon (le caller renvoie alors 200 sans effet).
    """
    existing = (
        db.query(models.WebhookEvent)
        .filter(models.WebhookEvent.event_id == event_id)
        .first()
    )
    if existing is not None:
        raise OrderError("duplicate_event")

    payment = (
        db.query(models.Payment)
        .filter(models.Payment.reference == payment_reference)
        .first()
    )
    if payment is None:
        raise OrderError("Paiement introuvable.")

    # Enregistre l'évènement AVANT d'appliquer l'effet (garantit l'idempotence).
    db.add(
        models.WebhookEvent(event_id=event_id, provider=provider, payload=payload)
    )

    payment.events = list(payment.events or []) + [
        {"type": new_status.value, "at": _now_iso(), "event_id": event_id}
    ]
    payment.status = new_status

    order = db.get(models.Order, payment.order_id)
    if new_status == models.PaymentStatus.SUCCESS and order is not None:
        # Un paiement réussi confirme la commande : le stock doit être réservé,
        # que la boutique réserve « au paiement » ou « à la confirmation » (RM-04).
        # _reserve_stock est idempotent (drapeau stock_reserved) : aucun double décompte.
        _reserve_stock(db, order)
        if order.status == models.OrderStatus.NEW:
            order.status = models.OrderStatus.CONFIRMED
            _add_history(
                db, order, models.OrderStatus.CONFIRMED, note="Paiement confirmé", actor="webhook"
            )
        _update_customer_totals(db, order)

    db.commit()
    db.refresh(payment)
    return payment


def refund_payment(db: Session, payment: models.Payment, actor: str | None = None) -> models.Payment:
    if payment.status != models.PaymentStatus.SUCCESS:
        raise OrderError("Seul un paiement réussi peut être remboursé.")
    payment.status = models.PaymentStatus.REFUNDED
    payment.events = list(payment.events or []) + [{"type": "refunded", "at": _now_iso()}]
    order = db.get(models.Order, payment.order_id)
    if order is not None and order.status != models.OrderStatus.REFUNDED:
        order.status = models.OrderStatus.REFUNDED
        _add_history(db, order, models.OrderStatus.REFUNDED, note="Remboursement", actor=actor)
        _release_stock(db, order)
    db.commit()
    db.refresh(payment)
    return payment


def _update_customer_totals(db: Session, order: models.Order) -> None:
    if order.customer_id is None:
        return
    customer = db.get(models.Customer, order.customer_id)
    if customer is None:
        return
    customer.orders_count += 1
    customer.total_spent += order.total


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
