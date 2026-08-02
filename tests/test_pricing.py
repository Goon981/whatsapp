"""Tarification serveur (RM-02) et montants entiers FCFA (RM-08)."""
from __future__ import annotations

import pytest

from app.services import pricing
from app.services.pricing import PricingError


def test_total_recomputed_from_active_prices(db_session, make_shop, make_product):
    """RM-02 : le total est calculé à partir des prix actifs, pas du client."""
    _, shop = make_shop()
    p = make_product(shop, price=2500, stock=10)

    priced = pricing.price_cart(db_session, shop.id, [{"product_id": p.id, "quantity": 3}])
    assert priced.subtotal == 7500
    assert priced.total == 7500
    assert isinstance(priced.total, int)  # RM-08


def test_promo_price_applied(db_session, make_shop, make_product):
    _, shop = make_shop()
    p = make_product(shop, price=4000, promo_price=3000, stock=5)
    priced = pricing.price_cart(db_session, shop.id, [{"product_id": p.id, "quantity": 2}])
    assert priced.subtotal == 6000  # promo appliquée


def test_insufficient_stock_rejected(db_session, make_shop, make_product):
    _, shop = make_shop()
    p = make_product(shop, price=1000, stock=2)
    with pytest.raises(PricingError):
        pricing.price_cart(db_session, shop.id, [{"product_id": p.id, "quantity": 5}])


def test_delivery_fee_added(db_session, make_shop, make_product):
    from app import models

    _, shop = make_shop()
    p = make_product(shop, price=1000, stock=10)
    zone = models.DeliveryZone(shop_id=shop.id, name="Akwa", fee=500)
    db_session.add(zone)
    db_session.commit()
    priced = pricing.price_cart(
        db_session, shop.id, [{"product_id": p.id, "quantity": 1}], delivery_zone=zone
    )
    assert priced.delivery_fee == 500
    assert priced.total == 1500
