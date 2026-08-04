"""Super-administration (HTML) — §7, §8. Réservée au rôle superadmin (RM-06)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import SESSION_COOKIE
from ..security import verify_token
from ..services import billing as billing_service
from ..services import stats as stats_service
from ..templating import templates

router = APIRouter(prefix="/admin", tags=["admin-ui"], include_in_schema=False)


def _current_admin(request: Request, db: Session) -> models.User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    user = db.get(models.User, int(payload.get("sub", 0)))
    if user and user.is_active and user.role == models.UserRole.SUPERADMIN:
        return user
    return None


def _guard(request: Request, db: Session):
    admin = _current_admin(request, db)
    if admin is None:
        return None, RedirectResponse("/app/login", status_code=303)
    return admin, None


def _audit(db: Session, admin: models.User, action: str, target: str, shop_id: int | None) -> None:
    db.add(models.AuditLog(actor=f"{admin.full_name} (#{admin.id})", action=action, target=target, shop_id=shop_id))


@router.get("", response_class=HTMLResponse)
def overview(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "admin/overview.html",
        {"active_tab": "overview", "o": stats_service.platform_overview(db)},
    )


@router.get("/billing", response_class=HTMLResponse)
def billing(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    # Application automatique des suspensions à chaque consultation (auto-enforce).
    billing_service.enforce_all(db)
    shops_list = (
        db.query(models.Shop)
        .filter(models.Shop.is_deleted.is_(False))
        .order_by(models.Shop.created_at.desc())
        .all()
    )
    rows = [
        {"shop": s, "sub": s.subscription, "state": billing_service.state_of(s, s.subscription)}
        for s in shops_list
    ]
    plans = [(p.value, billing_service.PLAN_LABELS[p.value]) for p in models.SubscriptionPlan]
    return templates.TemplateResponse(
        request, "admin/billing.html",
        {"active_tab": "billing", "rows": rows, "o": billing_service.overview(db), "plans": plans},
    )


@router.post("/billing/{shop_id}/mark-paid", response_class=HTMLResponse)
def billing_mark_paid(shop_id: int, request: Request, db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    shop = db.get(models.Shop, shop_id)
    if shop:
        billing_service.mark_paid(db, shop, actor=f"{admin.full_name} (#{admin.id})")
        _audit(db, admin, "subscription.mark_paid", shop.name, shop_id)
        db.commit()
    return RedirectResponse("/admin/billing", status_code=303)


@router.post("/billing/{shop_id}/plan", response_class=HTMLResponse)
def billing_change_plan(shop_id: int, request: Request, plan: str = Form(...), db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    shop = db.get(models.Shop, shop_id)
    if shop and plan in {p.value for p in models.SubscriptionPlan}:
        billing_service.change_plan(db, shop, models.SubscriptionPlan(plan))
        _audit(db, admin, "subscription.change_plan", f"{shop.name} → {plan}", shop_id)
        db.commit()
    return RedirectResponse("/admin/billing", status_code=303)


@router.get("/shops", response_class=HTMLResponse)
def shops(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    all_shops = (
        db.query(models.Shop)
        .filter(models.Shop.is_deleted.is_(False))
        .order_by(models.Shop.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "admin/shops.html", {"active_tab": "shops", "shops": all_shops}
    )


@router.post("/shops/{shop_id}/suspend", response_class=HTMLResponse)
def suspend(shop_id: int, request: Request, reason: str = Form("Non conforme"), db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    shop = db.get(models.Shop, shop_id)
    if shop:
        shop.status = models.ShopStatus.SUSPENDED
        shop.suspended_reason = reason
        _audit(db, admin, "shop.suspend", shop.name, shop_id)
        db.commit()
    return RedirectResponse("/admin/shops", status_code=303)


@router.post("/shops/{shop_id}/activate", response_class=HTMLResponse)
def activate(shop_id: int, request: Request, db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    shop = db.get(models.Shop, shop_id)
    if shop:
        shop.status = models.ShopStatus.ACTIVE
        shop.suspended_reason = None
        # Réactivation manuelle : lève le drapeau impayé et accorde une fenêtre de
        # courtoisie pour éviter une resuspension automatique immédiate.
        sub = shop.subscription
        if sub and sub.suspended_for_nonpayment:
            sub.suspended_for_nonpayment = False
            sub.status = models.SubscriptionStatus.ACTIVE
            end = sub.current_period_end
            if end is not None:
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                if end < datetime.now(timezone.utc):
                    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=7)
        _audit(db, admin, "shop.activate", shop.name, shop_id)
        db.commit()
    return RedirectResponse("/admin/shops", status_code=303)


@router.get("/incidents", response_class=HTMLResponse)
def incidents(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    items = (
        db.query(models.Payment)
        .filter(models.Payment.status.in_([models.PaymentStatus.FAILED, models.PaymentStatus.EXPIRED]))
        .order_by(models.Payment.created_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        request, "admin/incidents.html", {"active_tab": "incidents", "incidents": items}
    )


@router.get("/audit", response_class=HTMLResponse)
def audit(request: Request, db: Session = Depends(get_db)):
    admin, redirect = _guard(request, db)
    if redirect:
        return redirect
    logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        request, "admin/audit.html", {"active_tab": "audit", "logs": logs}
    )
