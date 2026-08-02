"""Parcours de commande complet (§15 Commande, WhatsApp, RM-01, RM-04)."""
from __future__ import annotations

from app import models


def _checkout_payload(product_id, qty=2):
    return {
        "items": [{"product_id": product_id, "quantity": qty}],
        "customer_name": "Jean Test",
        "customer_phone": "+237677000000",
        "payment_method": "cash_on_delivery",
        "is_pickup": True,
    }


def test_order_recorded_once(client, db_session, make_shop, make_product):
    """§15 : une commande est enregistrée une seule fois et visible au commerçant."""
    _, shop = make_shop()
    p = make_product(shop, price=1500, stock=10)

    resp = client.post(f"/api/shops/{shop.id}/checkout", json=_checkout_payload(p.id, 2))
    assert resp.status_code == 201
    data = resp.json()
    assert data["order"]["total"] == 3000
    assert "whatsapp_link" in data and data["whatsapp_link"].startswith("https://wa.me/")

    orders = db_session.query(models.Order).filter(models.Order.shop_id == shop.id).all()
    assert len(orders) == 1
    assert len(orders[0].items) == 1


def test_whatsapp_link_contains_reference_and_total(client, db_session, make_shop, make_product):
    """§15 WhatsApp : le message reprend référence, articles et total."""
    from urllib.parse import unquote

    _, shop = make_shop()
    p = make_product(shop, name="Ndole", price=3000, stock=5)
    resp = client.post(f"/api/shops/{shop.id}/checkout", json=_checkout_payload(p.id, 1))
    data = resp.json()
    decoded = unquote(data["whatsapp_link"])
    assert data["order"]["reference"] in decoded
    assert "Ndole" in decoded
    assert "3 000 FCFA" in decoded


def test_suspended_shop_checkout_blocked(client, db_session, make_shop, make_product):
    """RM-01 : une boutique suspendue est inaccessible au public."""
    _, shop = make_shop()
    p = make_product(shop, price=1000, stock=5)
    shop.status = models.ShopStatus.SUSPENDED
    db_session.commit()

    resp = client.post(f"/api/shops/{shop.id}/checkout", json=_checkout_payload(p.id, 1))
    assert resp.status_code == 404


def test_stock_reserved_on_confirmation(client, db_session, make_shop, make_product):
    """RM-04 : le stock est réservé à la confirmation quand la boutique le demande."""
    from app.security import create_token
    from app.services import orders as orders_service

    owner, shop = make_shop(reserve_stock_on_confirm=True)
    p = make_product(shop, price=1000, stock=10)
    resp = client.post(f"/api/shops/{shop.id}/checkout", json=_checkout_payload(p.id, 3))
    order_id = resp.json()["order"]["id"]

    order = db_session.get(models.Order, order_id)
    assert db_session.get(models.Product, p.id).stock == 10  # pas encore réservé

    orders_service.change_status(db_session, order, models.OrderStatus.CONFIRMED, actor="test")
    db_session.refresh(p)
    assert p.stock == 7  # 3 réservés à la confirmation


def test_min_order_amount_enforced(client, db_session, make_shop, make_product):
    _, shop = make_shop(min_order_amount=5000)
    p = make_product(shop, price=1000, stock=10)
    resp = client.post(f"/api/shops/{shop.id}/checkout", json=_checkout_payload(p.id, 2))
    assert resp.status_code == 422
