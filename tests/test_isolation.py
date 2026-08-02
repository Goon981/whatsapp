"""Isolation multi-tenant (RM-05, §15 « Isolation »)."""
from __future__ import annotations

import pytest

from app.services import pricing
from app.services.pricing import PricingError


def test_cannot_price_product_from_another_shop(db_session, make_shop, make_product):
    """Un produit d'une autre boutique n'est jamais visible dans le panier."""
    _, shop_a = make_shop("Shop A")
    _, shop_b = make_shop("Shop B")
    product_b = make_product(shop_b, name="Produit B", price=1000, stock=10)

    with pytest.raises(PricingError):
        pricing.price_cart(db_session, shop_a.id, [{"product_id": product_b.id, "quantity": 1}])


def test_merchant_cannot_read_other_shop_orders(client, db_session, make_shop, make_product):
    """RM-05 : un commerçant ne peut pas lire les commandes d'une autre boutique."""
    from app.security import create_token

    owner_a, shop_a = make_shop("Shop A")
    _, shop_b = make_shop("Shop B")

    token_a = create_token({"sub": str(owner_a.id), "role": "owner"})
    # owner_a tente de lister les commandes de shop_b -> 404 (ne révèle pas l'existence).
    resp = client.get(
        f"/api/shops/{shop_b.id}/orders",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404


def test_merchant_cannot_create_product_in_other_shop(client, db_session, make_shop):
    from app.security import create_token

    owner_a, _ = make_shop("Shop A")
    _, shop_b = make_shop("Shop B")
    token_a = create_token({"sub": str(owner_a.id), "role": "owner"})
    resp = client.post(
        f"/api/shops/{shop_b.id}/products",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Intrus", "price": 1000},
    )
    assert resp.status_code == 404
