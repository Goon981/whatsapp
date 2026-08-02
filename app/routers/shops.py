"""API boutiques (§13) : création, profil, thème, horaires, livraison, paiements."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_permission, require_shop_access
from ..models import utcnow
from ..utils import unique_shop_slug

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.post("", response_model=schemas.ShopOut, status_code=201)
def create_shop(
    data: schemas.ShopCreateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Shop:
    shop = models.Shop(
        owner_id=user.id,
        name=data.name,
        slug=unique_shop_slug(db, data.name),
        sector=data.sector,
        whatsapp_number=data.whatsapp_number,
        contact_phone=data.whatsapp_number,
        city=data.city,
        status=models.ShopStatus.ACTIVE,
    )
    db.add(shop)
    db.flush()
    # Le propriétaire est membre avec tous les droits.
    db.add(
        models.ShopMember(
            shop_id=shop.id,
            user_id=user.id,
            role=models.UserRole.OWNER,
            permissions={k: True for k in ["orders", "catalog", "stock", "settings", "customers", "stats"]},
        )
    )
    # Abonnement d'essai par défaut (§6.10).
    db.add(
        models.Subscription(
            shop_id=shop.id,
            plan=models.SubscriptionPlan.TRIAL,
            status=models.SubscriptionStatus.TRIALING,
            current_period_end=utcnow() + timedelta(days=14),
        )
    )
    db.commit()
    db.refresh(shop)
    return shop


@router.get("", response_model=list[schemas.ShopOut])
def my_shops(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.Shop]:
    """Liste uniquement les boutiques de l'utilisateur (RM-05)."""
    member_shop_ids = [
        m.shop_id
        for m in db.query(models.ShopMember).filter(models.ShopMember.user_id == user.id).all()
    ]
    return (
        db.query(models.Shop)
        .filter(
            models.Shop.is_deleted.is_(False),
            (models.Shop.owner_id == user.id) | (models.Shop.id.in_(member_shop_ids or [-1])),
        )
        .all()
    )


@router.get("/{shop_id}", response_model=schemas.ShopOut)
def get_shop(access=Depends(require_shop_access)) -> models.Shop:
    shop, _ = access
    return shop


@router.patch("/{shop_id}", response_model=schemas.ShopOut)
def update_shop(
    data: schemas.ShopUpdateIn,
    access=Depends(require_permission("settings")),
    db: Session = Depends(get_db),
) -> models.Shop:
    shop, _ = access
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop


# --- Zones de livraison ----------------------------------------------------- #
@router.post("/{shop_id}/delivery-zones", status_code=201)
def add_delivery_zone(
    name: str,
    fee: int = 0,
    fee_type: models.DeliveryFeeType = models.DeliveryFeeType.FIXED,
    estimated_delay: str | None = None,
    access=Depends(require_permission("settings")),
    db: Session = Depends(get_db),
) -> dict:
    shop, _ = access
    if fee < 0:
        raise HTTPException(422, "Les frais ne peuvent pas être négatifs.")
    zone = models.DeliveryZone(
        shop_id=shop.id, name=name, fee=fee, fee_type=fee_type, estimated_delay=estimated_delay
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return {"id": zone.id, "name": zone.name, "fee": zone.fee, "fee_type": zone.fee_type.value}


@router.get("/{shop_id}/delivery-zones")
def list_delivery_zones(access=Depends(require_shop_access), db: Session = Depends(get_db)) -> list[dict]:
    shop, _ = access
    zones = (
        db.query(models.DeliveryZone)
        .filter(models.DeliveryZone.shop_id == shop.id, models.DeliveryZone.is_active.is_(True))
        .all()
    )
    return [
        {"id": z.id, "name": z.name, "fee": z.fee, "fee_type": z.fee_type.value, "estimated_delay": z.estimated_delay}
        for z in zones
    ]
