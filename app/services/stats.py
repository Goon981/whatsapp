"""Agrégats statistiques par boutique et période (§6.9)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models

_PAID_OR_ACTIVE = (
    models.OrderStatus.CONFIRMED,
    models.OrderStatus.PREPARING,
    models.OrderStatus.READY,
    models.OrderStatus.DELIVERING,
    models.OrderStatus.DELIVERED,
)


def _revenue_since(db: Session, shop_id: int, since: datetime) -> int:
    total = (
        db.query(func.coalesce(func.sum(models.Order.total), 0))
        .filter(
            models.Order.shop_id == shop_id,
            models.Order.status.in_(_PAID_OR_ACTIVE),
            models.Order.created_at >= since,
        )
        .scalar()
    )
    return int(total or 0)


def revenue_series(db: Session, shop_id: int, days: int = 14) -> list[int]:
    """Chiffre d'affaires par jour sur les ``days`` derniers jours (pour la courbe)."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(models.Order.created_at, models.Order.total)
        .filter(
            models.Order.shop_id == shop_id,
            models.Order.status.in_(_PAID_OR_ACTIVE),
            models.Order.created_at >= start,
        )
        .all()
    )
    buckets = [0] * days
    for created_at, total in rows:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        idx = (created_at - start).days
        if 0 <= idx < days:
            buckets[idx] += int(total or 0)
    return buckets


def shop_dashboard(db: Session, shop_id: int) -> dict:
    """Renvoie les indicateurs clés du tableau de bord commerçant."""
    now = datetime.now(timezone.utc)
    day = now - timedelta(days=1)
    week = now - timedelta(days=7)
    month = now - timedelta(days=30)

    base = db.query(models.Order).filter(models.Order.shop_id == shop_id)
    total_orders = base.count()
    cancelled = base.filter(models.Order.status == models.OrderStatus.CANCELLED).count()
    pending_payments = (
        db.query(models.Payment)
        .filter(
            models.Payment.shop_id == shop_id,
            models.Payment.status == models.PaymentStatus.PENDING,
        )
        .count()
    )

    revenue_all = (
        db.query(func.coalesce(func.sum(models.Order.total), 0))
        .filter(models.Order.shop_id == shop_id, models.Order.status.in_(_PAID_OR_ACTIVE))
        .scalar()
    ) or 0
    paid_orders = base.filter(models.Order.status.in_(_PAID_OR_ACTIVE)).count()
    avg_basket = int(revenue_all / paid_orders) if paid_orders else 0

    # Meilleurs produits par quantité vendue.
    top = (
        db.query(
            models.OrderItem.product_name,
            func.sum(models.OrderItem.quantity).label("qty"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.OrderItem.shop_id == shop_id,
            models.Order.status.in_(_PAID_OR_ACTIVE),
        )
        .group_by(models.OrderItem.product_name)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    low_stock = (
        db.query(models.Product)
        .filter(
            models.Product.shop_id == shop_id,
            models.Product.is_archived.is_(False),
            models.Product.stock <= models.Product.low_stock_threshold,
        )
        .order_by(models.Product.stock.asc())
        .limit(5)
        .all()
    )

    new_customers = (
        db.query(models.Customer)
        .filter(models.Customer.shop_id == shop_id, models.Customer.created_at >= week)
        .count()
    )
    total_customers = (
        db.query(models.Customer).filter(models.Customer.shop_id == shop_id).count()
    )
    orders_in_progress = base.filter(
        models.Order.status.in_(
            [models.OrderStatus.NEW, models.OrderStatus.CONFIRMED,
             models.OrderStatus.PREPARING, models.OrderStatus.READY, models.OrderStatus.DELIVERING]
        )
    ).count()
    products_in_stock = (
        db.query(models.Product)
        .filter(models.Product.shop_id == shop_id, models.Product.is_archived.is_(False))
        .count()
    )
    products_sold = (
        db.query(func.coalesce(func.sum(models.OrderItem.quantity), 0))
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(models.OrderItem.shop_id == shop_id, models.Order.status.in_(_PAID_OR_ACTIVE))
        .scalar()
    ) or 0

    # Évolution du CA : 30 derniers jours vs 30 jours précédents.
    prev_month = _revenue_since_between(db, shop_id, now - timedelta(days=60), month)
    cur_month = _revenue_since(db, shop_id, month)
    revenue_delta = _pct_delta(cur_month, prev_month)

    return {
        "revenue_day": _revenue_since(db, shop_id, day),
        "revenue_week": _revenue_since(db, shop_id, week),
        "revenue_month": cur_month,
        "revenue_total": int(revenue_all),
        "revenue_delta": revenue_delta,
        "total_orders": total_orders,
        "orders_in_progress": orders_in_progress,
        "products_in_stock": products_in_stock,
        "products_sold": int(products_sold),
        "total_customers": total_customers,
        "avg_basket": avg_basket,
        "cancellation_rate": round((cancelled / total_orders * 100), 1) if total_orders else 0.0,
        "pending_payments": pending_payments,
        "top_products": [{"name": name, "quantity": int(qty)} for name, qty in top],
        "low_stock": [{"name": p.name, "stock": p.stock} for p in low_stock],
        "new_customers": new_customers,
        "series": revenue_series(db, shop_id, 14),
    }


def _revenue_since_between(db: Session, shop_id: int, start: datetime, end: datetime) -> int:
    total = (
        db.query(func.coalesce(func.sum(models.Order.total), 0))
        .filter(
            models.Order.shop_id == shop_id,
            models.Order.status.in_(_PAID_OR_ACTIVE),
            models.Order.created_at >= start,
            models.Order.created_at < end,
        )
        .scalar()
    )
    return int(total or 0)


def _pct_delta(current: int, previous: int) -> float:
    if previous <= 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 0)


def platform_overview(db: Session) -> dict:
    """Vue globale de la super-administration (§7)."""
    active_shops = db.query(models.Shop).filter(
        models.Shop.is_deleted.is_(False), models.Shop.status == models.ShopStatus.ACTIVE
    ).count()
    suspended = db.query(models.Shop).filter(
        models.Shop.status == models.ShopStatus.SUSPENDED
    ).count()
    total_orders = db.query(models.Order).count()
    total_gmv = (
        db.query(func.coalesce(func.sum(models.Order.total), 0))
        .filter(models.Order.status.in_(_PAID_OR_ACTIVE))
        .scalar()
    ) or 0
    users = db.query(models.User).count()
    failed_payments = (
        db.query(models.Payment).filter(models.Payment.status == models.PaymentStatus.FAILED).count()
    )
    return {
        "active_shops": active_shops,
        "suspended_shops": suspended,
        "total_users": users,
        "total_orders": total_orders,
        "gmv": int(total_gmv),
        "failed_payments": failed_payments,
    }
