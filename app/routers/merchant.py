"""Espace commerçant (HTML) — onboarding, dashboard, produits, commandes, réglages (§8).

Session par cookie httponly signé. Toute donnée est filtrée par la boutique de
l'utilisateur (RM-05).
"""
from __future__ import annotations

from datetime import timedelta
import hashlib
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from .. import models, ratelimit
from ..config import settings
from ..database import get_db
from ..deps import SESSION_COOKIE
from ..ratelimit import client_ip
from ..models import utcnow
from ..security import create_token, hash_password, verify_password, verify_token
from ..services import charts, mailer, media
from ..services import orders as orders_service
from ..services import stats as stats_service
from ..services.orders import OrderError
from ..services.theme import DEFAULT_BRAND, build_dark_palette, build_palette
from ..services.whatsapp import build_wa_link
from ..templating import templates
from ..utils import unique_shop_slug

logger = logging.getLogger("smartshop")

router = APIRouter(prefix="/app", tags=["merchant-ui"], include_in_schema=False)

# Connexion : 8 essais par quart d'heure, assez pour un mot de passe oublié,
# trop peu pour parcourir un dictionnaire.
LOGIN_LIMIT = 8
LOGIN_WINDOW = 900

# Teintes proposées à la personnalisation. Toutes sont assez soutenues pour
# porter du texte clair et rester lisibles une fois éclaircies en mode sombre :
# un pastel choisi au hasard donnait une barre supérieure délavée.
THEME_PRESETS = [
    ("Forêt", "#16824c"),
    ("Émeraude", "#0f766e"),
    ("Océan", "#0e6ba8"),
    ("Indigo", "#4340a8"),
    ("Prune", "#8a3a6b"),
    ("Rubis", "#b02f46"),
    ("Terre", "#a1512a"),
    ("Ocre", "#8f6b12"),
    ("Ardoise", "#3d5561"),
    ("Nuit", "#26303f"),
]

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


def _owned_category_id(db: Session, shop: models.Shop, raw: str) -> int | None:
    """Convertit un ``category_id`` de formulaire, en le refusant s'il est étranger.

    Le champ arrive du client : sans cette vérification, un commerçant peut
    rattacher son produit à la catégorie d'une autre boutique.
    """
    if not raw or not raw.strip().isdigit():
        return None
    category_id = int(raw.strip())
    exists = (
        db.query(models.Category.id)
        .filter(models.Category.id == category_id, models.Category.shop_id == shop.id)
        .first()
    )
    return category_id if exists else None


def _check_subscription_active(shop: models.Shop) -> bool:
    """La boutique a-t-elle un accès valide : abonnement payé ou essai en cours ?

    Seul l'essai était consulté. Un commerçant qui venait de payer restait donc
    renvoyé vers la page d'abonnement dès son essai expiré, sans moyen d'entrer
    dans son tableau de bord — et une boutique sans date d'essai (créée sans
    période d'essai) était bloquée d'emblée.
    """
    now = utcnow()

    sub = shop.subscription
    if sub is not None and sub.current_period_end is not None:
        if models.as_utc(sub.current_period_end) > now:
            return True

    if shop.trial_expires_at is not None:
        return models.as_utc(shop.trial_expires_at) > now

    # Ni abonnement ni essai enregistré : ne pas enfermer le commerçant dehors,
    # la suspension pour impayé est décidée par services/billing.enforce_all.
    return sub is None


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
    if user.role == models.UserRole.SUPERADMIN:
        return _redirect("/admin")
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

    # Sans plafond, un script pouvait essayer les mots de passe en continu. On
    # compte par IP *et* par identifiant visé : bloquer la seule IP laisserait
    # passer une attaque distribuée sur un compte connu.
    throttle_keys = [f"login:ip:{client_ip(request)}", f"login:id:{identifier.lower()}"]
    for key in throttle_keys:
        allowed, retry_after = ratelimit.hit(key, limit=LOGIN_LIMIT, window=LOGIN_WINDOW)
        if not allowed:
            return templates.TemplateResponse(
                request, "merchant/login.html",
                {
                    "mode": "login",
                    "error": (
                        "Trop de tentatives de connexion. "
                        f"Réessayez dans {retry_after} secondes."
                    ),
                },
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

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

    for key in throttle_keys:
        ratelimit.reset(key)
    if user.role == models.UserRole.SUPERADMIN:
        resp = _redirect("/admin")
    elif _active_shop(db, user):
        resp = _redirect("/app/dashboard")
    else:
        resp = _redirect("/app/onboarding")
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
    password_confirm: str = Form(""),
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
    elif password != password_confirm:
        # La concordance n'était vérifiée que par le script de la page : une
        # faute de frappe passait dès que le JavaScript ne s'exécutait pas, et
        # le commerçant se retrouvait avec un mot de passe qu'il ignorait.
        error = "Les deux mots de passe ne correspondent pas."
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


# --------------------------------------------------------------------------- #
# Mot de passe oublié
# --------------------------------------------------------------------------- #
# Le lien vaut une connexion : durée courte, et trois demandes par heure et par
# adresse IP pour ne pas transformer la route en robinet à e-mails.
RESET_MAX_AGE = 30 * 60
RESET_LIMIT = 3
RESET_WINDOW = 3600

# Réponse volontairement identique que le compte existe ou non : la distinguer
# permettrait de savoir quelles adresses sont inscrites sur la plateforme.
RESET_SENT_MESSAGE = (
    "Si un compte correspond, un lien de réinitialisation vient d'être envoyé. "
    "Le lien expire dans 30 minutes."
)


def _password_fingerprint(user: models.User) -> str:
    """Empreinte du mot de passe actuel, incluse dans le jeton.

    Elle rend le lien utilisable une seule fois sans stocker quoi que ce soit :
    la réinitialisation change le hachage, donc l'empreinte, donc tout jeton
    encore en circulation cesse d'être valide.
    """
    return hashlib.sha256((user.password_hash or "").encode()).hexdigest()[:16]


@router.get("/mot-de-passe-oublie", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "merchant/forgot_password.html", {"mode": "request"})


@router.post("/mot-de-passe-oublie", response_class=HTMLResponse)
def forgot_password_submit(
    request: Request,
    identifier: str = Form(...),
    db: Session = Depends(get_db),
):
    allowed, retry_after = ratelimit.hit(
        f"reset:{client_ip(request)}", limit=RESET_LIMIT, window=RESET_WINDOW
    )
    if not allowed:
        minutes = max(1, retry_after // 60)
        return templates.TemplateResponse(
            request, "merchant/forgot_password.html",
            {"mode": "request", "error": f"Trop de demandes. Réessayez dans {minutes} minutes."},
            status_code=429, headers={"Retry-After": str(retry_after)},
        )

    identifier = identifier.strip()
    user = (
        db.query(models.User)
        .filter((models.User.email == identifier) | (models.User.phone == identifier))
        .first()
    )

    delivered = False
    if user and user.email and user.is_active:
        token = create_token(
            {"reset": user.id, "pw": _password_fingerprint(user)}, max_age=RESET_MAX_AGE
        )
        link = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/app/reinitialiser?token={token}"
        delivered = mailer.send(
            user.email,
            "Réinitialisation de votre mot de passe BAOBAY",
            f"Bonjour {user.full_name or ''},\n\n"
            f"Pour choisir un nouveau mot de passe, ouvrez ce lien :\n{link}\n\n"
            "Le lien expire dans 30 minutes et ne fonctionne qu'une fois.\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n",
        )
        if not delivered:
            # L'envoi a échoué : le lien va dans le journal du serveur pour que
            # le support puisse le transmettre, plutôt que d'être perdu.
            logger.warning("Lien de réinitialisation non distribué pour l'utilisateur %s.", user.id)

    return templates.TemplateResponse(
        request, "merchant/forgot_password.html",
        {
            "mode": "sent",
            "message": RESET_SENT_MESSAGE,
            "mail_configured": mailer.is_configured(),
            "support": settings.SUPPORT_WHATSAPP,
        },
    )


def _reset_user(db: Session, token: str) -> models.User | None:
    payload = verify_token(token)
    if not payload or "reset" not in payload:
        return None
    user = db.get(models.User, int(payload["reset"]))
    if user is None or not user.is_active:
        return None
    if payload.get("pw") != _password_fingerprint(user):
        return None
    return user


@router.get("/reinitialiser", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = "", db: Session = Depends(get_db)):
    if _reset_user(db, token) is None:
        return templates.TemplateResponse(
            request, "merchant/forgot_password.html",
            {"mode": "request", "error": "Ce lien est expiré ou a déjà été utilisé."},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "merchant/forgot_password.html", {"mode": "reset", "token": token}
    )


@router.post("/reinitialiser", response_class=HTMLResponse)
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _reset_user(db, token)
    if user is None:
        return templates.TemplateResponse(
            request, "merchant/forgot_password.html",
            {"mode": "request", "error": "Ce lien est expiré ou a déjà été utilisé."},
            status_code=400,
        )

    error = None
    if len(password) < 8:
        error = "Le mot de passe doit contenir au moins 8 caractères."
    elif password != password_confirm:
        error = "Les deux mots de passe ne correspondent pas."
    if error:
        return templates.TemplateResponse(
            request, "merchant/forgot_password.html",
            {"mode": "reset", "token": token, "error": error}, status_code=422,
        )

    user.password_hash = hash_password(password)
    db.commit()

    # Le plafond de tentatives de connexion est levé : l'utilisateur vient de
    # prouver qu'il contrôle l'adresse, le laisser bloqué n'aurait aucun sens.
    for key in (f"login:id:{(user.email or '').lower()}", f"api-login:id:{(user.email or '').lower()}"):
        ratelimit.reset(key)

    resp = _redirect("/app/dashboard" if _active_shop(db, user) else "/app/onboarding")
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
    return templates.TemplateResponse(
        request, "merchant/onboarding.html",
        {"shop": None, "theme_presets": THEME_PRESETS, "default_theme": DEFAULT_BRAND},
    )


@router.post("/onboarding", response_class=HTMLResponse)
async def onboarding_submit(
    request: Request,
    name: str = Form(...),
    whatsapp_number: str = Form(...),
    sector: str = Form("general"),
    sector_other: str = Form(""),
    city: str = Form(""),
    theme_color: str = Form(DEFAULT_BRAND),
    logo: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if user is None:
        return _redirect("/app/login")
    # Secteur libre saisi via l'option « Autre ».
    if sector == "autre" and sector_other.strip():
        sector = sector_other.strip()

    # Logo conservé en base : le disque du conteneur est effacé à chaque
    # déploiement. La lecture est bornée — ``logo.file.read()`` chargeait tout
    # en mémoire — et un fichier refusé le dit, au lieu d'être silencieusement
    # ignoré par un ``except: pass``.
    logo_url = None
    logo_error = None
    if logo and logo.filename:
        try:
            logo_url = await media.store_upload(db, logo)
        except HTTPException as exc:
            logo_error = str(exc.detail)

    # Les nuances découlent de la couleur principale : les laisser au choix
    # produisait des combinaisons illisibles (texte blanc sur fond blanc).
    palette = build_palette(theme_color)

    shop = models.Shop(
        owner_id=user.id, name=name, slug=unique_shop_slug(db, name), sector=sector,
        whatsapp_number=whatsapp_number, contact_phone=whatsapp_number, city=city or None,
        status=models.ShopStatus.ACTIVE,
        theme_color=palette["brand"],
        secondary_color=palette["brand-050"],
        text_color=palette["on-brand"],
        logo_url=logo_url,
        trial_expires_at=utcnow() + timedelta(days=14),
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
    if logo_url:
        # Rattacher l'image à la boutique une fois son identifiant connu.
        blob = db.get(models.MediaFile, media.media_id(logo_url))
        if blob is not None:
            blob.shop_id = shop.id
    db.commit()
    # La boutique existe : la page de paiement peut présenter les formules
    # (« Continuer sans payer » mène au tableau de bord pendant l'essai).
    # Un logo refusé est signalé plutôt que perdu en silence.
    return _redirect("/app/payment?logo=refuse" if logo_error else "/app/payment")


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
            days_left = (models.as_utc(shop.trial_expires_at) - now).days
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
@router.get("/products/create", response_class=HTMLResponse)
def product_create_page(request: Request, db: Session = Depends(get_db)):
    """Page dédiée à la création d'un produit avec uploads multiples."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    categories = (
        db.query(models.Category)
        .filter(models.Category.shop_id == shop.id)
        .order_by(models.Category.position)
        .all()
    )
    return templates.TemplateResponse(
        request, "merchant/product_create.html",
        {"shop": shop, "categories": categories}
    )


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
async def create_product(
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
    files: list[UploadFile] = File(default=[]),
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
        category_id=_owned_category_id(db, shop, category_id),
        image_url=image_url.strip() or None, description=description.strip() or None,
    )
    db.add(product)
    db.flush()
    for v in _parse_variants(variants, shop.id, product.price):
        v.product_id = product.id
        db.add(v)
    db.commit()

    # Images du produit. Elles sont conservées en base : écrites sur le disque
    # du conteneur, elles disparaissaient au déploiement suivant.
    if files:
        position = 0
        for file in files:
            if file.content_type not in media.ALLOWED_TYPES:
                continue
            url = await media.store_upload(db, file, shop_id=shop.id)
            db.add(models.ProductImage(
                shop_id=shop.id,
                product_id=product.id,
                image_url=url,
                position=position,
                is_primary=(position == 0),
            ))
            position += 1

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


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def edit_product_page(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Affiche la page d'édition du produit avec galerie d'images."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    user, shop = ctx
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if not product:
        return _redirect("/app/products")

    images = (
        db.query(models.ProductImage)
        .filter(models.ProductImage.product_id == product_id)
        .order_by(models.ProductImage.position)
        .all()
    )
    categories = db.query(models.Category).filter(models.Category.shop_id == shop.id).all()

    return templates.TemplateResponse(
        request, "merchant/edit_product.html",
        {
            "shop": shop, "user": user, "product": product,
            "images": images, "categories": categories,
            "active_tab": "products",
        },
    )


@router.post("/products/{product_id}", response_class=HTMLResponse)
def update_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    price: int = Form(...),
    stock: int = Form(0),
    low_stock_threshold: int = Form(5),
    promo_price: str = Form(""),
    category_id: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    """Met à jour les informations du produit."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if not product:
        return _redirect("/app/products")

    product.name = name
    product.price = max(0, price)
    product.stock = max(0, stock)
    product.low_stock_threshold = max(0, low_stock_threshold)
    product.promo_price = int(promo_price) if promo_price.strip().isdigit() else None
    product.category_id = _owned_category_id(db, shop, category_id)
    product.description = description.strip() or None

    db.commit()
    return _redirect("/app/products")


# --------------------------------------------------------------------------- #
# Catégories
# --------------------------------------------------------------------------- #
@router.get("/categories", response_class=HTMLResponse)
def categories_page(request: Request, db: Session = Depends(get_db)):
    """Affiche la liste des catégories."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    user, shop = ctx
    categories = (
        db.query(models.Category)
        .filter(models.Category.shop_id == shop.id)
        .order_by(models.Category.position)
        .all()
    )
    return templates.TemplateResponse(
        request, "merchant/categories.html",
        {"shop": shop, "user": user, "categories": categories, "active_tab": "categories"},
    )


@router.post("/categories", response_class=HTMLResponse)
def create_category(
    name: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Crée une nouvelle catégorie."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    user, shop = ctx

    name = name.strip()
    if not name:
        return _redirect("/app/categories")

    # Vérifier si la catégorie existe déjà
    existing = (
        db.query(models.Category)
        .filter(models.Category.shop_id == shop.id, models.Category.name == name)
        .first()
    )
    if existing:
        return _redirect("/app/categories")

    # Trouver la position maximale
    max_position = (
        db.query(models.Category)
        .filter(models.Category.shop_id == shop.id)
        .with_entities(models.Category.position.isouter())
        .order_by(models.Category.position.desc())
        .first()
    )
    position = (max_position[0] or 0) + 1 if max_position and max_position[0] else 1

    category = models.Category(
        shop_id=shop.id,
        name=name,
        position=position,
        is_active=True,
    )
    db.add(category)
    db.commit()
    return _redirect("/app/categories")


@router.post("/categories/{category_id}/delete", response_class=HTMLResponse)
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Supprime une catégorie."""
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    user, shop = ctx

    category = (
        db.query(models.Category)
        .filter(models.Category.id == category_id, models.Category.shop_id == shop.id)
        .first()
    )
    if not category:
        return _redirect("/app/categories")

    # Vérifier si des produits de cette boutique utilisent la catégorie.
    product_count = (
        db.query(models.Product)
        .filter(
            models.Product.category_id == category_id,
            models.Product.shop_id == shop.id,
        )
        .count()
    )

    if product_count > 0:
        # Ne pas supprimer si des produits l'utilisent
        return _redirect("/app/categories")

    db.delete(category)
    db.commit()
    return _redirect("/app/categories")


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
        request, "merchant/settings.html",
        {
            "shop": shop, "active_tab": "settings", "zones": zones,
            "theme_presets": THEME_PRESETS,
        },
    )


@router.get("/theme-preview")
def theme_preview(request: Request, color: str = "", db: Session = Depends(get_db)):
    """Palette dérivée d'une couleur, pour l'aperçu en direct.

    Servie aux réglages comme à la création de boutique — d'où l'exigence d'un
    simple compte connecté et non d'une boutique, qui n'existe pas encore à la
    création. L'aperçu appelle le même code que le rendu des pages : dupliquer
    le calcul en JavaScript avait laissé les deux formules diverger, et le
    commerçant choisissait sa couleur sur un aperçu qui ne disait pas la vérité.
    """
    if _current_user(request, db) is None:
        raise HTTPException(status_code=403, detail="Session expirée")
    return {"light": build_palette(color), "dark": build_dark_palette(color)}


@router.post("/settings", response_class=HTMLResponse)
async def settings_submit(request: Request, db: Session = Depends(get_db)):
    ctx, redirect = _require_shop(request, db)
    if redirect:
        return redirect
    _, shop = ctx
    form = await request.form()
    shop.name = (form.get("name") or shop.name).strip()
    shop.description = (form.get("description") or "").strip() or None
    # Même dérivation qu'à la création : les nuances suivent la couleur choisie.
    settings_palette = build_palette(form.get("theme_color") or shop.theme_color)
    shop.theme_color = settings_palette["brand"]
    shop.secondary_color = settings_palette["brand-050"]
    shop.text_color = settings_palette["on-brand"]
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
    user = _current_user(request, db)
    if user is None:
        return _redirect("/app/login")

    shop = _active_shop(db, user)
    if shop is None:
        return _redirect("/app/onboarding")
    return templates.TemplateResponse(request, "merchant/payment.html", {"shop": shop, "user": user})


