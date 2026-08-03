"""Storefront public (HTML) — parcours client (§5.2, §8).

Rendu serveur mobile-first. Une boutique suspendue est inaccessible (RM-01).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..templating import templates
from ..services.whatsapp import build_wa_link

router = APIRouter(tags=["storefront"], include_in_schema=False)

_STATUS_LABELS = {
    "new": "Nouvelle",
    "confirmed": "Confirmée",
    "preparing": "En préparation",
    "ready": "Prête",
    "delivering": "En livraison",
    "delivered": "Livrée",
    "cancelled": "Annulée",
    "refunded": "Remboursée",
}
_STATUS_CLASS = {
    "new": "blue", "confirmed": "green", "preparing": "amber", "ready": "amber",
    "delivering": "blue", "delivered": "green", "cancelled": "red", "refunded": "gray",
}


def _get_public_shop(db: Session, slug: str) -> models.Shop:
    shop = db.query(models.Shop).filter(models.Shop.slug == slug).first()
    if shop is None or shop.is_deleted or shop.status != models.ShopStatus.ACTIVE:
        raise HTTPException(404, "Boutique introuvable ou indisponible.")
    return shop


@router.get("/s/{slug}", response_class=HTMLResponse)
def shop_home(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = None,
    category: int | None = None,
):
    shop = _get_public_shop(db, slug)
    query = db.query(models.Product).filter(
        models.Product.shop_id == shop.id,
        models.Product.is_archived.is_(False),
        models.Product.status != models.ProductStatus.HIDDEN,
    )
    if q:
        query = query.filter(models.Product.name.ilike(f"%{q}%"))
    if category:
        query = query.filter(models.Product.category_id == category)
    products = query.order_by(models.Product.created_at.desc()).all()
    categories = (
        db.query(models.Category)
        .filter(models.Category.shop_id == shop.id, models.Category.is_active.is_(True))
        .order_by(models.Category.position)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "storefront/shop.html",
        {"shop": shop, "products": products, "categories": categories, "q": q, "current_category": category},
    )


@router.get("/s/{slug}/p/{product_id}", response_class=HTMLResponse)
def product_page(slug: str, product_id: int, request: Request, db: Session = Depends(get_db)):
    shop = _get_public_shop(db, slug)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.shop_id == shop.id,
            models.Product.is_archived.is_(False),
        )
        .first()
    )
    if product is None or product.status == models.ProductStatus.HIDDEN:
        raise HTTPException(404, "Produit introuvable.")
    return templates.TemplateResponse(
        request, "storefront/product.html",
        {"shop": shop, "product": product, "back_url": f"/s/{shop.slug}"},
    )


@router.get("/s/{slug}/panier", response_class=HTMLResponse)
def cart_page(slug: str, request: Request, db: Session = Depends(get_db)):
    shop = _get_public_shop(db, slug)
    return templates.TemplateResponse(
        request, "storefront/cart.html", {"shop": shop, "back_url": f"/s/{shop.slug}"}
    )


@router.get("/s/{slug}/commande", response_class=HTMLResponse)
def checkout_page(slug: str, request: Request, db: Session = Depends(get_db)):
    shop = _get_public_shop(db, slug)
    zones = (
        db.query(models.DeliveryZone)
        .filter(models.DeliveryZone.shop_id == shop.id, models.DeliveryZone.is_active.is_(True))
        .all()
    )
    return templates.TemplateResponse(
        request, "storefront/checkout.html",
        {"shop": shop, "zones": zones, "back_url": f"/s/{shop.slug}/panier"},
    )


@router.get("/s/{slug}/confirmation/{reference}", response_class=HTMLResponse)
def confirmation_page(slug: str, reference: str, request: Request, db: Session = Depends(get_db)):
    shop = _get_public_shop(db, slug)
    order = (
        db.query(models.Order)
        .filter(models.Order.reference == reference, models.Order.shop_id == shop.id)
        .first()
    )
    if order is None:
        raise HTTPException(404, "Commande introuvable.")
    instructions = None
    if order.payments:
        instructions = None  # instructions déjà affichées à la création
    return templates.TemplateResponse(
        request,
        "storefront/confirmation.html",
        {"shop": shop, "order": order, "whatsapp_link": build_wa_link(shop, order), "payment_instructions": instructions},
    )


@router.get("/s/{slug}/suivi/{reference}", response_class=HTMLResponse)
def track_page(slug: str, reference: str, request: Request, db: Session = Depends(get_db)):
    shop = _get_public_shop(db, slug)
    order = (
        db.query(models.Order)
        .filter(models.Order.reference == reference, models.Order.shop_id == shop.id)
        .first()
    )
    if order is None:
        raise HTTPException(404, "Commande introuvable.")
    return templates.TemplateResponse(
        request,
        "storefront/track.html",
        {
            "shop": shop,
            "order": order,
            "status_label": _STATUS_LABELS.get(order.status.value, order.status.value),
            "status_class": _STATUS_CLASS.get(order.status.value, "gray"),
            "status_labels": _STATUS_LABELS,
        },
    )
