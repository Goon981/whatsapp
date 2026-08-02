"""API super-administration (§7, §13) : boutiques, suspension, incidents, audit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_superadmin
from ..services import stats as stats_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _audit(db: Session, actor: models.User, action: str, target: str, shop_id: int | None = None) -> None:
    db.add(
        models.AuditLog(
            actor=f"{actor.full_name} (#{actor.id})",
            action=action,
            target=target,
            shop_id=shop_id,
        )
    )


@router.get("/overview")
def overview(_: models.User = Depends(require_superadmin), db: Session = Depends(get_db)) -> dict:
    return stats_service.platform_overview(db)


@router.get("/shops")
def list_all_shops(
    _: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
    status: models.ShopStatus | None = None,
) -> list[dict]:
    query = db.query(models.Shop).filter(models.Shop.is_deleted.is_(False))
    if status is not None:
        query = query.filter(models.Shop.status == status)
    shops = query.order_by(models.Shop.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "slug": s.slug,
            "status": s.status.value,
            "owner_id": s.owner_id,
            "city": s.city,
        }
        for s in shops
    ]


@router.post("/shops/{shop_id}/suspend")
def suspend_shop(
    shop_id: int,
    reason: str = "Non conforme",
    admin: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict:
    """RM-01 : suspend une boutique ; données conservées, public bloqué."""
    shop = db.get(models.Shop, shop_id)
    if shop is None:
        raise HTTPException(404, "Boutique introuvable.")
    shop.status = models.ShopStatus.SUSPENDED
    shop.suspended_reason = reason
    _audit(db, admin, "shop.suspend", shop.name, shop_id)
    db.commit()
    return {"status": shop.status.value}


@router.post("/shops/{shop_id}/activate")
def activate_shop(
    shop_id: int,
    admin: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict:
    shop = db.get(models.Shop, shop_id)
    if shop is None:
        raise HTTPException(404, "Boutique introuvable.")
    shop.status = models.ShopStatus.ACTIVE
    shop.suspended_reason = None
    _audit(db, admin, "shop.activate", shop.name, shop_id)
    db.commit()
    return {"status": shop.status.value}


@router.get("/incidents")
def payment_incidents(
    _: models.User = Depends(require_superadmin), db: Session = Depends(get_db)
) -> list[dict]:
    """Incidents de paiement : transactions échouées/expirées (§7)."""
    incidents = (
        db.query(models.Payment)
        .filter(
            models.Payment.status.in_(
                [models.PaymentStatus.FAILED, models.PaymentStatus.EXPIRED]
            )
        )
        .order_by(models.Payment.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": p.id,
            "reference": p.reference,
            "shop_id": p.shop_id,
            "order_id": p.order_id,
            "amount": p.amount,
            "status": p.status.value,
        }
        for p in incidents
    ]


@router.get("/audit")
def audit_log(
    _: models.User = Depends(require_superadmin), db: Session = Depends(get_db)
) -> list[dict]:
    logs = (
        db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(100).all()
    )
    return [
        {
            "actor": log.actor,
            "action": log.action,
            "target": log.target,
            "shop_id": log.shop_id,
            "at": log.created_at.isoformat(),
        }
        for log in logs
    ]
