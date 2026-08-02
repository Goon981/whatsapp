"""Authentification, onboarding et bout-en-bout HTML (§15 Onboarding, Catalogue)."""
from __future__ import annotations

from app import models


def test_register_and_create_shop_via_api(client, db_session):
    """§15 Onboarding : un commerçant crée son compte et publie sa boutique."""
    reg = client.post("/api/auth/register", json={
        "full_name": "Nouveau Vendeur", "email": "vendeur@test.cm",
        "password": "motdepasse1", "accept_terms": True,
    })
    assert reg.status_code == 201
    token = reg.json()["access_token"]

    shop = client.post("/api/shops", headers={"Authorization": f"Bearer {token}"}, json={
        "name": "Ma Boutique", "whatsapp_number": "+237690000000",
    })
    assert shop.status_code == 201
    shop_id = shop.json()["id"]

    # §15 Catalogue : créer un produit, il apparaît côté client.
    prod = client.post(f"/api/shops/{shop_id}/products", headers={"Authorization": f"Bearer {token}"}, json={
        "name": "Article", "price": 1500, "stock": 5,
    })
    assert prod.status_code == 201

    slug = shop.json()["slug"]
    public = client.get(f"/s/{slug}")
    assert public.status_code == 200
    assert "Article" in public.text


def test_wrong_password_rejected(client, db_session, make_shop):
    make_shop("Shop")
    resp = client.post("/api/auth/login", json={
        "identifier": "owner-shop@test.cm", "password": "mauvais",
    })
    assert resp.status_code == 401


def test_login_returns_token(client, db_session, make_shop):
    make_shop("Shop")
    resp = client.post("/api/auth/login", json={
        "identifier": "owner-shop@test.cm", "password": "password123",
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
