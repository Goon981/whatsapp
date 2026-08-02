"""Paiements : webhook signé idempotent (RM-07), confirmation serveur (§6.7), RM-03."""
from __future__ import annotations

import json

from app import models
from app.security import sign_payload
from app.services import orders as orders_service


def _make_order_with_payment(db_session, shop, product):
    from app.services import pricing

    priced = pricing.price_cart(db_session, shop.id, [{"product_id": product.id, "quantity": 1}])
    order = orders_service.create_order(
        db_session, shop, priced,
        customer_name="Client", customer_phone="+237677000000",
        payment_method=models.PaymentMethod.MTN_MOMO, is_pickup=True,
    )
    payment = orders_service.initiate_payment(db_session, order, models.PaymentMethod.MTN_MOMO)
    return order, payment


def test_webhook_rejects_bad_signature(client, db_session, make_shop, make_product):
    _, shop = make_shop()
    p = make_product(shop, price=2000, stock=5)
    _, payment = _make_order_with_payment(db_session, shop, p)

    body = json.dumps({
        "event_id": "evt-1", "payment_reference": payment.reference, "status": "success",
    })
    resp = client.post(
        "/api/payments/webhook", content=body,
        headers={"X-Signature": "wrong", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_webhook_success_confirms_order(client, db_session, make_shop, make_product):
    """§6.7 : la confirmation vient du webhook serveur, pas de l'écran client."""
    _, shop = make_shop(reserve_stock_on_confirm=False)
    p = make_product(shop, price=2000, stock=5)
    order, payment = _make_order_with_payment(db_session, shop, p)

    body = json.dumps({
        "event_id": "evt-success", "payment_reference": payment.reference, "status": "success",
    })
    resp = client.post(
        "/api/payments/webhook", content=body,
        headers={"X-Signature": sign_payload(body.encode()), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    db_session.refresh(order)
    db_session.refresh(payment)
    assert payment.status == models.PaymentStatus.SUCCESS
    assert order.status == models.OrderStatus.CONFIRMED
    # Réservation au paiement (RM-04) puisque reserve_stock_on_confirm=False.
    db_session.refresh(p)
    assert p.stock == 4


def test_webhook_is_idempotent(client, db_session, make_shop, make_product):
    """RM-07 : le même event_id ne double jamais l'effet."""
    _, shop = make_shop(reserve_stock_on_confirm=False)
    p = make_product(shop, price=2000, stock=5)
    order, payment = _make_order_with_payment(db_session, shop, p)

    body = json.dumps({
        "event_id": "evt-dup", "payment_reference": payment.reference, "status": "success",
    })
    headers = {"X-Signature": sign_payload(body.encode()), "Content-Type": "application/json"}

    first = client.post("/api/payments/webhook", content=body, headers=headers)
    second = client.post("/api/payments/webhook", content=body, headers=headers)
    assert first.json()["status"] == "ok"
    assert second.json()["status"] == "ignored"  # doublon ignoré

    db_session.refresh(p)
    assert p.stock == 4  # stock réservé une seule fois, pas deux


def test_webhook_reserves_stock_even_when_reserve_on_confirm(client, db_session, make_shop, make_product):
    """RM-04 : un paiement réussi réserve le stock même si la boutique réserve « à la confirmation »."""
    _, shop = make_shop(reserve_stock_on_confirm=True)
    p = make_product(shop, price=2000, stock=5)
    order, payment = _make_order_with_payment(db_session, shop, p)

    body = json.dumps({
        "event_id": "evt-confirm-shop", "payment_reference": payment.reference, "status": "success",
    })
    client.post(
        "/api/payments/webhook", content=body,
        headers={"X-Signature": sign_payload(body.encode()), "Content-Type": "application/json"},
    )
    db_session.refresh(p)
    assert p.stock == 4  # stock réservé via la confirmation par paiement


def test_paid_order_cannot_be_deleted(client, db_session, make_shop, make_product):
    """RM-03 : une commande payée ne peut pas être supprimée."""
    _, shop = make_shop(reserve_stock_on_confirm=False)
    p = make_product(shop, price=2000, stock=5)
    order, payment = _make_order_with_payment(db_session, shop, p)

    body = json.dumps({
        "event_id": "evt-paid", "payment_reference": payment.reference, "status": "success",
    })
    client.post(
        "/api/payments/webhook", content=body,
        headers={"X-Signature": sign_payload(body.encode()), "Content-Type": "application/json"},
    )
    db_session.refresh(order)
    assert order.is_paid is True
    assert orders_service.can_delete(order) is False
