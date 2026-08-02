"""API commandes (§13) : création publique (checkout), gestion commerçant."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_permission, require_shop_access
from ..services import orders as orders_service
from ..services import pricing
from ..services.orders import OrderError
from ..services.pricing import PricingError
from ..services.whatsapp import build_wa_link

router = APIRouter(tags=["orders"])


def _load_active_shop(db: Session, shop_id: int) -> models.Shop:
    shop = db.get(models.Shop, shop_id)
    if shop is None or shop.is_deleted or shop.status != models.ShopStatus.ACTIVE:
        # RM-01 : une boutique suspendue est inaccessible au public.
        raise HTTPException(404, "Boutique indisponible.")
    return shop


# --------------------------------------------------------------------------- #
# Checkout public (client) — enregistre la commande une seule fois (§15)
# --------------------------------------------------------------------------- #
@router.post("/api/shops/{shop_id}/checkout", response_model=schemas.CheckoutOut, status_code=201)
def checkout(shop_id: int, data: schemas.CheckoutIn, db: Session = Depends(get_db)):
    shop = _load_active_shop(db, shop_id)

    zone = None
    if data.delivery_zone_id and not data.is_pickup:
        zone = (
            db.query(models.DeliveryZone)
            .filter(
                models.DeliveryZone.id == data.delivery_zone_id,
                models.DeliveryZone.shop_id == shop.id,
            )
            .first()
        )
        if zone is None:
            raise HTTPException(422, "Zone de livraison invalide.")

    try:
        priced = pricing.price_cart(
            db,
            shop.id,
            [item.model_dump() for item in data.items],
            delivery_zone=zone,
        )
        order = orders_service.create_order(
            db,
            shop,
            priced,
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            payment_method=data.payment_method,
            delivery_city=data.delivery_city,
            delivery_district=data.delivery_district,
            delivery_details=data.delivery_details,
            delivery_zone=zone,
            is_pickup=data.is_pickup,
            customer_note=data.customer_note,
            marketing_consent=data.marketing_consent,
        )
    except (PricingError, OrderError) as exc:
        raise HTTPException(422, str(exc))

    instructions = None
    if data.payment_method != models.PaymentMethod.CASH_ON_DELIVERY:
        payment = orders_service.initiate_payment(db, order, data.payment_method)
        provider = orders_service.payments_service.get_provider(payment.provider)
        instructions = provider.initialize(order, data.payment_method).instructions

    return schemas.CheckoutOut(
        order=order,
        whatsapp_link=build_wa_link(shop, order),
        payment_instructions=instructions,
    )


@router.get("/api/orders/{reference}", response_model=schemas.OrderOut)
def track_order(reference: str, db: Session = Depends(get_db)):
    """Suivi public d'une commande par référence (le client suit son statut, §5.2)."""
    order = db.query(models.Order).filter(models.Order.reference == reference).first()
    if order is None:
        raise HTTPException(404, "Commande introuvable.")
    return order


# --------------------------------------------------------------------------- #
# Gestion commerçant
# --------------------------------------------------------------------------- #
@router.get("/api/shops/{shop_id}/orders", response_model=list[schemas.OrderOut])
def list_orders(
    access=Depends(require_permission("orders")),
    db: Session = Depends(get_db),
    status: models.OrderStatus | None = None,
):
    shop, _ = access
    query = db.query(models.Order).filter(models.Order.shop_id == shop.id)
    if status is not None:
        query = query.filter(models.Order.status == status)
    return query.order_by(models.Order.created_at.desc()).all()


@router.get("/api/shops/{shop_id}/orders/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, access=Depends(require_permission("orders")), db: Session = Depends(get_db)):
    shop, _ = access
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.shop_id == shop.id)
        .first()
    )
    if order is None:
        raise HTTPException(404, "Commande introuvable.")
    return order


@router.post("/api/shops/{shop_id}/orders/{order_id}/status", response_model=schemas.OrderOut)
def change_order_status(
    order_id: int,
    data: schemas.StatusChangeIn,
    access=Depends(require_permission("orders")),
    db: Session = Depends(get_db),
):
    shop, membership = access
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.shop_id == shop.id)
        .first()
    )
    if order is None:
        raise HTTPException(404, "Commande introuvable.")
    actor = "commerçant" if membership is None else membership.role.value
    try:
        return orders_service.change_status(db, order, data.status, actor=actor, note=data.note)
    except OrderError as exc:
        raise HTTPException(409, str(exc))
