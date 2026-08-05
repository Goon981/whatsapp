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
from ..services import charts
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


def _check_subscription_active(shop: models.Shop) -> bool:
    """Vérifie si la boutique a un abonnement actif (trial ou payant)"""
    try:
        if not shop.trial_expires_at:
            return False
        return shop.trial_expires_at > utcnow()
    except Exception:
        return True  # Par défaut, laisser accès


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
    resp = _redirect("/app/payment")
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

    # Créer une boutique automatiquement avec trial de 14 jours
    shop_name = full_name.split()[0] if full_name else "Ma Boutique"
    shop = models.Shop(
        owner_id=user.id,
        name=shop_name,
        slug=unique_shop_slug(db, shop_name),
        trial_expires_at=utcnow() + timedelta(days=14),
    )
    db.add(shop)
    db.commit()

    resp = _redirect("/app/payment")
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
    sector_other: str = Form(""),
    city: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if user is None:
        return _redirect("/app/login")
    # Secteur libre saisi via l'option « Autre ».
    if sector == "autre" and sector_other.strip():
        sector = sector_other.strip()
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
    """Retourne (user, shop) ou une réponse de redirection/blocage.

    Si la boutique est suspendue (impayé ou décision admin), on affiche une page
    de régularisation au lieu du tableau de bord.
    """
    user = _current_user(request, db)
    if user is None:
        return None, _redirect("/app/login")
    shop = _active_shop(db, user)
    if shop is None:
        return None, _redirect("/app/onboarding")
    if shop.status == models.ShopStatus.SUSPENDED:
        return None, templates.TemplateResponse(
            request, "merchant/suspended.html",
            {"shop": shop, "reason": shop.suspended_reason, "support_number": settings.SUPPORT_WHATSAPP},
            status_code=403,
        )
    return (user, shop), None


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    user, shop = ctx

    # Vérifier si l'abonnement est expiré
    if not _check_subscription_active(shop):
        return _redirect("/app/payment")

    stats = stats_service.shop_dashboard(db, shop.id)
    recent_orders = (
        db.query(models.Order)
        .filter(models.Order.shop_id == shop.id)
        .order_by(models.Order.created_at.desc())
        .limit(4)
        .all()
    )

    # Calcul du statut d'abonnement
    now = utcnow()
    trial_status = "TRIAL"
    days_left = 0
    try:
        if shop.trial_expires_at:
            days_left = (shop.trial_expires_at - now).days
            if days_left < 0:
                trial_status = "EXPIRED"
            elif days_left == 0:
                trial_status = "LAST_DAY"
    except Exception:
        trial_status = "TRIAL"  # Défaut

    return templates.TemplateResponse(
        request, "merchant/dashboard.html",
        {
            "shop": shop, "active_tab": "dashboard", "stats": stats,
            "first_name": user.full_name.split(" ")[0],
            "recent_orders": recent_orders,
            "chart": charts.line_chart(stats["series"]), "on_dark": True,
            "status_labels": STATUS_LABELS, "status_class": STATUS_CLASS,
            "public_base": settings.PUBLIC_BASE_URL,
            "trial_status": trial_status,
            "days_left": max(0, days_left),
        },
    )


@router.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    stats = stats_service.shop_dashboard(db, shop.id)
    return templates.TemplateResponse(
        request, "merchant/stats.html",
        {
            "shop": shop, "active_tab": "stats", "stats": stats,
            "chart": charts.line_chart(stats["series"]),
        },
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    user, shop = ctx
    initials = "".join(part[0] for part in user.full_name.split()[:2]).upper() or "?"
    plan = shop.subscription.plan.value if shop.subscription else "trial"
    plan_labels = {"trial": "Essai", "starter": "Starter", "business": "Business", "premium": "Premium"}
    return templates.TemplateResponse(
        request, "merchant/profile.html",
        {
            "shop": shop, "user": user, "active_tab": "profile",
            "stats": stats_service.shop_dashboard(db, shop.id),
            "initials": initials, "plan_label": plan_labels.get(plan, "Pro"),
        },
    )


# --------------------------------------------------------------------------- #
# Produits
# --------------------------------------------------------------------------- #
@router.get("/products/new", response_class=HTMLResponse)
async def product_new(request: Request, db: Session = Depends(get_db)):
    """Page d'ajout de produit avec upload d'images."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect

    html = """<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ajouter un produit - SmartShop</title>
    <link rel="stylesheet" href="/static/css/app.css">
    <style>
        .photo-zone { border: 2px dashed #007a49; border-radius: 12px; padding: 40px 20px; text-align: center; background: #f0f8f5; cursor: pointer; margin-bottom: 20px; }
        .photo-zone:hover { background: #e8f5e9; }
        #preview { max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 20px; display: none; }
        #imageInput { display: none; }
        .loading { color: #007a49; font-weight: 600; display: none; }
        .loading.show { display: block; }
    </style>
</head>
<body>
    <header class="topbar">
        <a href="/app/products" class="icon-btn">←</a>
        <strong>Ajouter un produit</strong>
        <span class="top-spacer"></span>
    </header>

    <main class="container page">
        <section class="content">
            <form id="productForm" method="post" action="/app/products">
                <!-- ZONE D'UPLOAD D'IMAGES -->
                <div class="photo-zone" onclick="document.getElementById('imageInput').click()">
                    <div style="font-size: 48px; margin-bottom: 12px;">📷</div>
                    <div style="font-weight: 600; color: #007a49; font-size: 16px; margin-bottom: 4px;">Cliquez pour ajouter une photo</div>
                    <div style="font-size: 13px; color: #666;">JPG, PNG, GIF - Max 5 MB</div>
                </div>

                <img id="preview">
                <div id="loading" class="loading">⏳ Chargement...</div>
                <input type="file" id="imageInput" accept="image/*">
                <input type="hidden" id="imageUrl" name="image_url">

                <!-- FORMULAIRE PRODUIT -->
                <div style="margin-bottom: 20px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">Nom du produit *</label>
                    <input type="text" name="name" placeholder="Ex. Robe en wax" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px;">
                </div>

                <div style="margin-bottom: 20px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">Description</label>
                    <textarea name="description" placeholder="Décrivez votre produit..." style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; resize: vertical; min-height: 100px;"></textarea>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
                    <div>
                        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Prix (FCFA) *</label>
                        <input type="number" name="price" placeholder="15 000" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px;">
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Stock</label>
                        <input type="number" name="stock" placeholder="10" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px;">
                    </div>
                </div>

                <div style="margin-bottom: 20px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">Catégorie</label>
                    <select name="category" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px;">
                        <option value="">Choisir une catégorie</option>
                        <option value="Vêtements">Vêtements</option>
                        <option value="Chaussures">Chaussures</option>
                        <option value="Accessoires">Accessoires</option>
                        <option value="Électronique">Électronique</option>
                        <option value="Autre">Autre</option>
                    </select>
                </div>

                <button type="submit" class="primary sticky-cta">Publier le produit</button>
            </form>
        </section>
    </main>

    <script>
        const imageInput = document.getElementById('imageInput');
        const preview = document.getElementById('preview');
        const loading = document.getElementById('loading');
        const imageUrl = document.getElementById('imageUrl');
        const photoZone = document.querySelector('.photo-zone');

        imageInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            loading.classList.add('show');
            photoZone.style.display = 'none';

            try {
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/uploads/product-image', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    preview.src = data.url;
                    preview.style.display = 'block';
                    imageUrl.value = data.url;
                } else {
                    alert('Erreur: ' + (data.error || 'Upload echoue'));
                }
            } catch (err) {
                alert('Erreur: ' + err.message);
            } finally {
                loading.classList.remove('show');
            }
        });
    </script>
</body>
</html>
    """
    return html


@router.get("/products", response_class=HTMLResponse)
def products_page(
    request: Request, db: Session = Depends(get_db),
    q: str | None = None, filter: str | None = None,
):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    base = db.query(models.Product).filter(
        models.Product.shop_id == shop.id, models.Product.is_archived.is_(False)
    )
    all_products = base.all()
    counts = {
        "all": len(all_products),
        "in_stock": sum(1 for p in all_products if p.stock > 0),
        "out": sum(1 for p in all_products if p.stock <= 0),
    }
    query = base
    if q:
        query = query.filter(models.Product.name.ilike(f"%{q}%"))
    if filter == "in_stock":
        query = query.filter(models.Product.stock > 0)
    elif filter == "out":
        query = query.filter(models.Product.stock <= 0)
    products = query.order_by(models.Product.created_at.desc()).all()
    categories = db.query(models.Category).filter(models.Category.shop_id == shop.id).all()
    return templates.TemplateResponse(
        request, "merchant/products.html",
        {
            "shop": shop, "active_tab": "products", "products": products,
            "categories": categories, "counts": counts, "q": q, "filter": filter,
        },
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


@router.post("/products/{product_id}/toggle", response_class=HTMLResponse)
def toggle_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Bascule la visibilité du produit en boutique (interrupteur de la maquette)."""
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
        if product.status == models.ProductStatus.HIDDEN:
            # Réaffiche : disponible si stock, sinon rupture.
            product.status = (
                models.ProductStatus.AVAILABLE if product.stock > 0
                else models.ProductStatus.OUT_OF_STOCK
            )
        else:
            product.status = models.ProductStatus.HIDDEN
        db.commit()
    return _redirect("/app/products")


# --------------------------------------------------------------------------- #
# Commandes
# --------------------------------------------------------------------------- #
@router.get("/orders", response_class=HTMLResponse)
def orders_page(
    request: Request, db: Session = Depends(get_db),
    status: str | None = None, q: str | None = None,
):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    query = db.query(models.Order).filter(models.Order.shop_id == shop.id)
    if status and status in STATUS_LABELS:
        query = query.filter(models.Order.status == models.OrderStatus(status))
    if q:
        like = f"%{q}%"
        query = query.filter(
            models.Order.reference.ilike(like) | models.Order.customer_name.ilike(like)
        )
    orders = query.order_by(models.Order.created_at.desc()).all()
    return templates.TemplateResponse(
        request, "merchant/orders.html",
        {
            "shop": shop, "active_tab": "orders", "orders": orders, "q": q,
            "current_status": status, "status_labels": STATUS_LABELS, "status_class": STATUS_CLASS,
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


@router.get("/payment", response_class=HTMLResponse)
async def payment_page(request: Request, db: Session = Depends(get_db)):
    """Page de paiement - choix du plan et moyens de paiement."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect

    return templates.TemplateResponse(request, "merchant/payment.html", ctx)

    # OLD INLINE HTML BELOW (REMOVED)
    html = """
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Abonnement & Paiement - SmartShop</title>
        <link rel="stylesheet" href="/static/css/app.css">
        <style>
            .trial-banner { background: #e8f5e9; border: 1px solid #4caf50; border-radius: 8px; padding: 16px; margin-bottom: 24px; text-align: center; }
            .trial-banner strong { display: block; color: #2e7d32; font-size: 16px; margin-top: 8px; }
            .trial-banner small { display: block; color: #558b2f; margin-top: 4px; }
            .plans-grid { display: grid; gap: 12px; margin-bottom: 20px; }
            .plan-card { border: 2px solid #ddd; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s; background: #fff; text-align: left; }
            .plan-card:hover { border-color: #007a49; background: #f0f8f5; }
            .plan-card.selected { border: 2px solid #007a49; background: #f0f8f5; }
            .plan-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
            .plan-name { font-weight: 600; color: #007a49; display: block; margin-bottom: 4px; }
            .plan-price { font-size: 18px; font-weight: bold; color: #007a49; }
            .plan-per-day { font-size: 12px; color: #999; margin-top: 8px; display: block; }
            .payment-methods { display: grid; gap: 12px; margin-bottom: 20px; }
            .payment-method { border: 1px solid #ddd; border-radius: 8px; padding: 16px; text-align: center; cursor: pointer; background: #fff; transition: all 0.2s; }
            .payment-method:hover { border-color: #007a49; background: #f0f8f5; }
            .support-banner { background: #fff3e0; border: 1px solid #ff9800; border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 20px; font-size: 13px; color: #e65100; }
            #skipBtn { width: 100%; padding: 14px; border: 2px solid #007a49; background: transparent; color: #007a49; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 12px; }
            #skipBtn:hover { background: #f0f8f5; }
        </style>
    </head>
    <body>
        <header class="topbar">
            <a href="/app" class="icon-btn">←</a>
            <strong>Abonnement & Paiement</strong>
            <span class="top-spacer"></span>
        </header>

        <main class="container page">
            <section class="content">
                <div class="trial-banner">
                    <div>✓</div>
                    <strong>Vous avez 14 jours pour payer</strong>
                    <small>Choisissez un plan ou continuez sans payer pour accéder au tableau de bord</small>
                </div>

                <h3>Choisissez votre plan</h3>
                <div class="plans-grid">
                    <button class="plan-card" onclick="selectPlan('starter', this)">
                        <div class="plan-header">
                            <div>
                                <span class="plan-name">Démarrage</span>
                                <span style="font-size: 13px; color: #666;">1 mois</span>
                            </div>
                            <span class="plan-price">5 000 FCFA</span>
                        </div>
                        <span class="plan-per-day">166 FCFA/jour</span>
                    </button>

                    <button class="plan-card" onclick="selectPlan('business', this)">
                        <div class="plan-header">
                            <div>
                                <span class="plan-name">Croissance</span>
                                <span style="font-size: 13px; color: #666;">3 mois</span>
                            </div>
                            <span class="plan-price">12 000 FCFA</span>
                        </div>
                        <span class="plan-per-day">133 FCFA/jour • Économie 3 000 FCFA</span>
                    </button>

                    <button class="plan-card" onclick="selectPlan('premium', this)">
                        <div class="plan-header">
                            <div>
                                <span class="plan-name">Pro annuel</span>
                                <span style="font-size: 13px; color: #666;">12 mois</span>
                            </div>
                            <span class="plan-price">50 000 FCFA</span>
                        </div>
                        <span class="plan-per-day">137 FCFA/jour • Économie 10 000 FCFA</span>
                    </button>
                </div>

                <h3>Moyens de paiement</h3>
                <div class="payment-methods">
                    <button class="payment-method">📱 MTN Mobile Money</button>
                    <button class="payment-method">🟠 Orange Money</button>
                </div>

                <div class="support-banner">
                    <b>Support :</b><br>
                    +237 690088572
                </div>

                <button class="primary sticky-cta" id="confirmBtn" onclick="confirmPayment()" disabled style="font-size: 18px; font-weight: 700; letter-spacing: 0.5px; box-shadow: 0 4px 12px rgba(0,122,73,0.3); transition: all 0.3s; background: linear-gradient(135deg, #007a49 0%, #005f38 100%); border: none;">
                    💳 Confirmer le paiement
                </button>
                <button id="skipBtn" onclick="window.location.href='/app'">Continuer sans payer</button>
            </section>
        </main>

        <script>
            let selectedPlan = null;
            function selectPlan(planName, element) {
                document.querySelectorAll('.plan-card').forEach(card => {
                    card.classList.remove('selected');
                });
                element.classList.add('selected');
                selectedPlan = planName;
                document.getElementById('confirmBtn').disabled = false;
            }
            function confirmPayment() {
                if (!selectedPlan) return;
                const names = {'starter': 'Démarrage (5000)', 'business': 'Croissance (12000)', 'premium': 'Pro (50000)'};
                alert('Plan: ' + names[selectedPlan] + '\\n\\nRedirigé vers MTN/Orange');
            }
        </script>
    </body>
    </html>
    """
    return html
