"""Calcul des montants — TOUJOURS côté serveur (RM-02) et en entiers FCFA (RM-08).

Le client transmet uniquement des identifiants et des quantités ; jamais des prix.
Le serveur relit les prix actifs, vérifie la disponibilité et recompose le total.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .. import models


class PricingError(Exception):
    """Erreur métier de tarification (produit indisponible, stock insuffisant…)."""


@dataclass
class PricedLine:
    product: models.Product
    variant: models.ProductVariant | None
    quantity: int
    unit_price: int
    line_total: int

    @property
    def label(self) -> str:
        if self.variant:
            return f"{self.product.name} ({self.variant.name})"
        return self.product.name


@dataclass
class PricedCart:
    lines: list[PricedLine] = field(default_factory=list)
    subtotal: int = 0
    delivery_fee: int = 0
    discount: int = 0

    @property
    def total(self) -> int:
        return max(0, self.subtotal + self.delivery_fee - self.discount)


def _variant_unit_price(product: models.Product, variant: models.ProductVariant | None) -> int:
    """Prix unitaire effectif : override de variante si défini, sinon prix produit (promo incluse)."""
    if variant is not None and variant.price is not None:
        return variant.price
    return product.effective_price


def price_cart(
    db: Session,
    shop_id: int,
    raw_items: list[dict],
    *,
    delivery_zone: models.DeliveryZone | None = None,
    discount: int = 0,
    check_stock: bool = True,
) -> PricedCart:
    """Recompose un panier à partir de ``[{product_id, variant_id?, quantity}]``.

    Toutes les entités sont filtrées par ``shop_id`` (RM-05). Lève ``PricingError``
    si un produit est absent, masqué, archivé ou en stock insuffisant.
    """
    cart = PricedCart()
    if not raw_items:
        raise PricingError("Le panier est vide.")

    for item in raw_items:
        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise PricingError("Ligne de panier invalide.")
        if quantity <= 0:
            raise PricingError("La quantité doit être positive.")

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == product_id,
                models.Product.shop_id == shop_id,  # isolation multi-tenant
                models.Product.is_archived.is_(False),
            )
            .first()
        )
        if product is None:
            raise PricingError("Un produit du panier n'existe plus.")
        if product.status == models.ProductStatus.HIDDEN:
            raise PricingError(f"« {product.name} » n'est plus disponible.")

        variant = None
        variant_id = item.get("variant_id")
        if variant_id:
            variant = (
                db.query(models.ProductVariant)
                .filter(
                    models.ProductVariant.id == int(variant_id),
                    models.ProductVariant.product_id == product.id,
                    models.ProductVariant.shop_id == shop_id,
                    models.ProductVariant.is_active.is_(True),
                )
                .first()
            )
            if variant is None:
                raise PricingError(f"Variante indisponible pour « {product.name} ».")

        available = variant.stock if variant is not None else product.stock
        is_preorder = product.status == models.ProductStatus.PREORDER
        if check_stock and not is_preorder and available < quantity:
            raise PricingError(
                f"Stock insuffisant pour « {product.name} » (disponible : {available})."
            )

        unit_price = _variant_unit_price(product, variant)
        line_total = unit_price * quantity
        cart.lines.append(
            PricedLine(product, variant, quantity, unit_price, line_total)
        )
        cart.subtotal += line_total

    if delivery_zone is not None and delivery_zone.fee_type != models.DeliveryFeeType.PICKUP:
        cart.delivery_fee = delivery_zone.fee
    cart.discount = max(0, int(discount))
    return cart


def format_fcfa(amount: int) -> str:
    """Formate un montant entier en FCFA avec séparateurs de milliers."""
    return f"{amount:,}".replace(",", " ") + " FCFA"
