"""Accès aux pages commerçant selon l'état de l'abonnement.

Le contrôle n'était appelé que par le tableau de bord : un commerçant sans
essai valide ni abonnement en était renvoyé, puis se rendait directement sur
``/app/products`` ou ``/app/orders`` et continuait d'exploiter sa boutique.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app import models
from app.models import utcnow

# Pages qui exigent un accès valide.
PAGES_PROTEGEES = [
    "/app/dashboard",
    "/app/products",
    "/app/products/create",
    "/app/orders",
    "/app/stats",
    "/app/customers",
    "/app/settings",
    "/app/categories",
]

# Pages qui doivent rester atteignables sans abonnement, sans quoi le
# commerçant ne pourrait ni payer ni se déconnecter.
PAGES_OUVERTES = ["/app/payment", "/app/profile"]


@pytest.fixture()
def commercant(client, db_session, make_shop):
    owner, shop = make_shop("Boutique Abonnement")

    def connecte():
        client.post(
            "/app/login",
            data={"identifier": owner.email, "password": "password123"},
            follow_redirects=False,
        )

    def essai(jours: int):
        shop.trial_expires_at = utcnow() + timedelta(days=jours)
        db_session.commit()

    connecte()
    return shop, essai


@pytest.mark.parametrize("page", PAGES_PROTEGEES)
def test_essai_en_cours_donne_acces(client, commercant, page):
    _, essai = commercant
    essai(5)
    assert client.get(page, follow_redirects=False).status_code == 200


@pytest.mark.parametrize("page", PAGES_PROTEGEES)
def test_essai_expire_renvoie_au_paiement(client, commercant, page):
    _, essai = commercant
    essai(-1)
    resp = client.get(page, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/app/payment")


@pytest.mark.parametrize("page", PAGES_OUVERTES)
def test_pages_de_regularisation_restent_ouvertes(client, commercant, page):
    """Bloquer celles-ci enfermerait le commerçant dehors sans moyen de payer."""
    _, essai = commercant
    essai(-1)
    assert client.get(page, follow_redirects=False).status_code == 200


def test_abonnement_paye_donne_acces_apres_expiration_de_l_essai(client, db_session, commercant):
    shop, essai = commercant
    essai(-1)
    db_session.add(models.Subscription(
        shop_id=shop.id,
        plan=models.SubscriptionPlan.STARTER,
        status=models.SubscriptionStatus.ACTIVE,
        current_period_end=utcnow() + timedelta(days=30),
    ))
    db_session.commit()

    assert client.get("/app/dashboard", follow_redirects=False).status_code == 200


def test_creation_de_produit_bloquee_sans_acces(client, db_session, commercant):
    """La page était protégée, l'envoi du formulaire devait l'être aussi."""
    _, essai = commercant
    essai(-1)
    resp = client.post(
        "/app/products",
        data={"name": "Produit interdit", "price": "1000"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/app/payment")
    assert db_session.query(models.Product).count() == 0


def test_boutique_suspendue_voit_la_page_de_regularisation(client, db_session, commercant):
    shop, essai = commercant
    essai(30)
    shop.status = models.ShopStatus.SUSPENDED
    shop.suspended_reason = "Abonnement impayé"
    db_session.commit()

    resp = client.get("/app/dashboard", follow_redirects=False)
    assert resp.status_code == 403
    assert "impayé" in resp.text or "Abonnement" in resp.text


def test_initier_un_paiement_n_active_aucun_abonnement(client, db_session, commercant):
    """Une demande envoyée n'est pas un paiement encaissé.

    Seuls le webhook signé et le super-administrateur activent un abonnement.
    """
    shop, essai = commercant
    essai(5)
    avant = shop.subscription

    client.post(
        "/api/billing/campay/initiate",
        params={"shop_id": shop.id, "plan": "starter", "phone": "237670000000"},
    )

    db_session.refresh(shop)
    assert shop.subscription is avant
    if avant is not None:
        assert avant.status != models.SubscriptionStatus.ACTIVE
