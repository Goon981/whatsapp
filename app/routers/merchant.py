"""Espace commerçant (HTML) — onboarding, dashboard, produits, commandes, réglages (§8).

Session par cookie httponly signé. Toute donnée est filtrée par la boutique de
l'utilisateur (RM-05).
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import SESSION_COOKIE
from ..models import utcnow
from ..security import create_token, hash_password, verify_password, verify_token
from ..services import orders as orders_service
from ..services import stats as stats_service
from ..services.orders import OrderError
from ..services.whatsapp import build_wa_link
from ..templating import templates
from ..utils import unique_shop_slug

router = APIRouter(prefix="/app", tags=["merchant-ui"], include_in_schema=False)

STATUS_LABELS = {
    "new": "Nouvelle", "confirmed": "Confirmée", "preparing": "En préparation",
    "ready": "Prête", "delivering": "En livraison", "delivered": "Livrée",
    "cancelled": "Annulée", "refunded": "Remboursée",
}
STATUS_CLASS = {
    "new": "blue", "confirmed": "green", "preparing": "amber", "ready": "amber",
    "delivering": "blue", "delivered": "green", "cancelled": "red", "refunded": "gray",
}
PAYMENT_LABELS = {
    "mtn_momo": "MTN MoMo", "orange_money": "Orange Money", "cash_on_delivery": "À la livraison",
}


# --------------------------------------------------------------------------- #
# Helpers de session
# --------------------------------------------------------------------------- #
def _current_user(request: Request, db: Session) -> models.User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    user = db.get(models.User, int(payload.get("sub", 0)))
    return user if user and user.is_active else None


def _active_shop(db: Session, user: models.User) -> models.Shop | None:
    return (
        db.query(models.Shop)
        .filter(models.Shop.owner_id == user.id, models.Shop.is_deleted.is_(False))
        .order_by(models.Shop.created_at.asc())
        .first()
    )


def _set_session(response: RedirectResponse, user: models.User) -> None:
    token = create_token({"sub": str(user.id), "role": user.role.value})
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax",
        secure=settings.COOKIE_SECURE, max_age=settings.SESSION_MAX_AGE,
    )


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user is None:
        return _redirect("/app/login")
    return _redirect("/app/dashboard" if _active_shop(db, user) else "/app/onboarding")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "merchant/login.html", {"mode": "login"})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    identifier = identifier.strip()
    user = (
        db.query(models.User)
        .filter((models.User.email == identifier) | (models.User.phone == identifier))
        .first()
    )
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "merchant/login.html",
            {"mode": "login", "error": "Identifiants invalides."}, status_code=401,
        )
    resp = _redirect("/app")
    _set_session(resp, user)
    return resp


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "merchant/login.html", {"mode": "register"})


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    full_name: str = Form(...),
    password: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    accept_terms: str = Form(None),
    db: Session = Depends(get_db),
):
    email = email.strip() or None
    phone = phone.strip() or None
    error = None
    if not accept_terms:
        error = "Vous devez accepter les conditions."
    elif not email and not phone:
        error = "Renseignez un e-mail ou un téléphone."
    elif len(password) < 8:
        error = "Le mot de passe doit contenir au moins 8 caractères."
    elif email and db.query(models.User).filter(models.User.email == email).first():
        error = "Cet e-mail est déjà utilisé."
    elif phone and db.query(models.User).filter(models.User.phone == phone).first():
        error = "Ce téléphone est déjà utilisé."
    if error:
        return templates.TemplateResponse(
            request, "merchant/login.html", {"mode": "register", "error": error}, status_code=422
        )
    user = models.User(
        full_name=full_name, email=email, phone=phone,
        password_hash=hash_password(password), role=models.UserRole.OWNER,
        accepted_terms_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    resp = _redirect("/app/onboarding")
    _set_session(resp, user)
    return resp


@router.get("/logout")
def logout():
    resp = _redirect("/app/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# --------------------------------------------------------------------------- #
# Onboarding
# --------------------------------------------------------------------------- #
@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user is None:
        return _redirect("/app/login")
    if _active_shop(db, user):
        return _redirect("/app/dashboard")
    return templates.TemplateResponse(request, "merchant/onboarding.html", {"shop": None})


@router.post("/onboarding", response_class=HTMLResponse)
def onboarding_submit(
    request: Request,
    name: str = Form(...),
    whatsapp_number: str = Form(...),
    sector: str = Form("general"),
    city: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if user is None:
        return _redirect("/app/login")
    shop = models.Shop(
        owner_id=user.id, name=name, slug=unique_shop_slug(db, name), sector=sector,
        whatsapp_number=whatsapp_number, contact_phone=whatsapp_number, city=city or None,
        status=models.ShopStatus.ACTIVE,
    )
    db.add(shop)
    db.flush()
    db.add(models.ShopMember(
        shop_id=shop.id, user_id=user.id, role=models.UserRole.OWNER,
        permissions={k: True for k in ["orders", "catalog", "stock", "settings", "customers", "stats"]},
    ))
    db.add(models.Subscription(
        shop_id=shop.id, plan=models.SubscriptionPlan.TRIAL,
        status=models.SubscriptionStatus.TRIALING, current_period_end=utcnow() + timedelta(days=14),
    ))
    db.commit()
    return _redirect("/app/dashboard")


# --------------------------------------------------------------------------- #
# Dépendance de page protégée
# --------------------------------------------------------------------------- #
def _require_shop(request: Request, db: Session):
    """Retourne (user, shop) ou une RedirectResponse."""
    user = _current_user(request, db)
    if user is None:
        return None, _redirect("/app/login")
    shop = _active_shop(db, user)
    if shop is None:
        return None, _redirect("/app/onboarding")
    return (user, shop), None


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    return templates.TemplateResponse(
        request, "merchant/dashboard.html",
        {
            "shop": shop, "active_tab": "dashboard",
            "stats": stats_service.shop_dashboard(db, shop.id),
            "public_base": settings.PUBLIC_BASE_URL,
        },
    )


# --------------------------------------------------------------------------- #
# Produits
# --------------------------------------------------------------------------- #
@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    products = (
        db.query(models.Product)
        .filter(models.Product.shop_id == shop.id, models.Product.is_archived.is_(False))
        .order_by(models.Product.created_at.desc())
        .all()
    )
    categories = db.query(models.Category).filter(models.Category.shop_id == shop.id).all()
    return templates.TemplateResponse(
        request, "merchant/products.html",
        {"shop": shop, "active_tab": "products", "products": products, "categories": categories},
    )


def _parse_variants(raw: str, shop_id: int, base_price: int) -> list[models.ProductVariant]:
    variants: list[models.ProductVariant] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        name = parts[0]
        price = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        stock = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        variants.append(models.ProductVariant(shop_id=shop_id, name=name, price=price, stock=stock))
    return variants


@router.post("/products", response_class=HTMLResponse)
def create_product(
    request: Request,
    name: str = Form(...),
    price: int = Form(...),
    stock: int = Form(0),
    low_stock_threshold: int = Form(5),
    promo_price: str = Form(""),
    category_id: str = Form(""),
    image_url: str = Form(""),
    description: str = Form(""),
    variants: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    product = models.Product(
        shop_id=shop.id, name=name, price=max(0, price), stock=max(0, stock),
        low_stock_threshold=max(0, low_stock_threshold),
        promo_price=int(promo_price) if promo_price.strip().isdigit() else None,
        category_id=int(category_id) if category_id.strip().isdigit() else None,
        image_url=image_url.strip() or None, description=description.strip() or None,
    )
    db.add(product)
    db.flush()
    for v in _parse_variants(variants, shop.id, product.price):
        v.product_id = product.id
        db.add(v)
    db.commit()
    return _redirect("/app/products")


@router.post("/products/{product_id}/archive", response_class=HTMLResponse)
def archive_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if product:
        product.is_archived = True  # RM-09 suppression logique
        db.commit()
    return _redirect("/app/products")


# --------------------------------------------------------------------------- #
# Commandes
# --------------------------------------------------------------------------- #
@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request, db: Session = Depends(get_db), status: str | None = None):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    query = db.query(models.Order).filter(models.Order.shop_id == shop.id)
    if status and status in STATUS_LABELS:
        query = query.filter(models.Order.status == models.OrderStatus(status))
    orders = query.order_by(models.Order.created_at.desc()).all()
    return templates.TemplateResponse(
        request, "merchant/orders.html",
        {
            "shop": shop, "active_tab": "orders", "orders": orders,
            "current_status": status, "status_labels": STATUS_LABELS, "status_class": STATUS_CLASS,
            "statuses": [(k, v) for k, v in STATUS_LABELS.items()],
        },
    )


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.shop_id == shop.id)
        .first()
    )
    if order is None:
        return _redirect("/app/orders")
    next_statuses = [
        (s.value, STATUS_LABELS[s.value])
        for s in orders_service._ALLOWED_TRANSITIONS.get(order.status, set())
    ]
    return templates.TemplateResponse(
        request, "merchant/order_detail.html",
        {
            "shop": shop, "active_tab": "orders", "order": order,
            "status_labels": STATUS_LABELS, "status_class": STATUS_CLASS,
            "payment_label": PAYMENT_LABELS.get(order.payment_method.value, order.payment_method.value),
            "next_statuses": next_statuses, "whatsapp_link": build_wa_link(shop, order),
        },
    )


@router.post("/orders/{order_id}/status", response_class=HTMLResponse)
def order_status(order_id: int, request: Request, status: str = Form(...), db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.shop_id == shop.id)
        .first()
    )
    if order and status in STATUS_LABELS:
        try:
            orders_service.change_status(db, order, models.OrderStatus(status), actor="commerçant")
        except OrderError:
            pass
    return _redirect(f"/app/orders/{order_id}")


# --------------------------------------------------------------------------- #
# Clients
# --------------------------------------------------------------------------- #
@router.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    customers = (
        db.query(models.Customer)
        .filter(models.Customer.shop_id == shop.id)
        .order_by(models.Customer.total_spent.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "merchant/customers.html",
        {"shop": shop, "active_tab": "customers", "customers": customers},
    )


# --------------------------------------------------------------------------- #
# Réglages
# --------------------------------------------------------------------------- #
_BOOL_FIELDS = ("is_open", "accept_mtn_momo", "accept_orange_money", "accept_cash_on_delivery", "reserve_stock_on_confirm")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    zones = db.query(models.DeliveryZone).filter(models.DeliveryZone.shop_id == shop.id).all()
    return templates.TemplateResponse(
        request, "merchant/settings.html", {"shop": shop, "active_tab": "settings", "zones": zones}
    )


@router.post("/settings", response_class=HTMLResponse)
async def settings_submit(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    form = await request.form()
    shop.name = (form.get("name") or shop.name).strip()
    shop.description = (form.get("description") or "").strip() or None
    shop.theme_color = form.get("theme_color") or shop.theme_color
    shop.logo_url = (form.get("logo_url") or "").strip() or None
    shop.whatsapp_number = (form.get("whatsapp_number") or "").strip() or None
    shop.contact_phone = (form.get("contact_phone") or "").strip() or None
    shop.city = (form.get("city") or "").strip() or None
    shop.address = (form.get("address") or "").strip() or None
    shop.opening_hours = (form.get("opening_hours") or "").strip() or None
    shop.closed_message = (form.get("closed_message") or "").strip() or None
    try:
        shop.min_order_amount = max(0, int(form.get("min_order_amount") or 0))
    except ValueError:
        pass
    for field in _BOOL_FIELDS:
        setattr(shop, field, form.get(field) is not None)
    db.commit()
    return _redirect("/app/settings")


@router.post("/delivery-zones", response_class=HTMLResponse)
def add_zone(request: Request, name: str = Form(...), fee: int = Form(0), db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    db.add(models.DeliveryZone(shop_id=shop.id, name=name.strip(), fee=max(0, fee)))
    db.commit()
    return _redirect("/app/settings")
