"""Confirmation du mot de passe, réinitialisation, et routes qui ne doivent plus répondre.

Ces cas couvrent des défauts constatés en production : une confirmation de mot
de passe vérifiée uniquement par le navigateur, un lien de réinitialisation
absent, et des routes de test qui écrivaient en base sans authentification.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app import models, ratelimit
from app.models import utcnow
from app.routers.merchant import _password_fingerprint
from app.security import create_token, hash_password, verify_password


@pytest.fixture(autouse=True)
def _clear_ratelimit():
    """Les compteurs vivent dans le processus : les vider entre les tests."""
    ratelimit._ATTEMPTS.clear()
    yield
    ratelimit._ATTEMPTS.clear()


def _register(client, **overrides):
    data = {
        "full_name": "Awa Nkeng",
        "email": "awa@test.cm",
        "password": "motdepasse1",
        "password_confirm": "motdepasse1",
        "accept_terms": "on",
    }
    data.update(overrides)
    return client.post("/app/register", data=data, follow_redirects=False)


# --------------------------------------------------------------------------- #
# Confirmation du mot de passe à l'inscription
# --------------------------------------------------------------------------- #
def test_inscription_refuse_deux_mots_de_passe_differents(client, db_session):
    resp = _register(client, password_confirm="autre-mot-de-passe")
    assert resp.status_code == 422
    assert "correspondent" in resp.text
    assert db_session.query(models.User).count() == 0


def test_inscription_refuse_confirmation_absente(client, db_session):
    """Le champ manque dès que le script de la page ne s'exécute pas."""
    resp = client.post(
        "/app/register",
        data={"full_name": "Awa", "email": "awa@test.cm",
              "password": "motdepasse1", "accept_terms": "on"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert db_session.query(models.User).count() == 0


def test_inscription_acceptee_quand_les_deux_correspondent(client, db_session):
    assert _register(client).status_code == 303
    user = db_session.query(models.User).one()
    assert verify_password("motdepasse1", user.password_hash)


# --------------------------------------------------------------------------- #
# Réinitialisation du mot de passe
# --------------------------------------------------------------------------- #
@pytest.fixture()
def user_avec_email(db_session):
    user = models.User(
        full_name="Awa Nkeng", email="awa@test.cm",
        password_hash=hash_password("ancien-mot-de-passe"),
        role=models.UserRole.OWNER, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _reset_token(user):
    return create_token({"reset": user.id, "pw": _password_fingerprint(user)}, max_age=1800)


def test_demande_ne_revele_pas_si_le_compte_existe(client, user_avec_email):
    """Des réponses différentes permettraient d'énumérer les comptes inscrits."""
    connu = client.post("/app/mot-de-passe-oublie", data={"identifier": "awa@test.cm"})
    inconnu = client.post("/app/mot-de-passe-oublie", data={"identifier": "personne@test.cm"})
    assert connu.status_code == inconnu.status_code == 200
    assert connu.text == inconnu.text


def test_lien_valide_change_le_mot_de_passe_et_connecte(client, db_session, user_avec_email):
    token = _reset_token(user_avec_email)
    resp = client.post(
        "/app/reinitialiser",
        data={"token": token, "password": "nouveau-mot-de-passe", "password_confirm": "nouveau-mot-de-passe"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "smartshop_session" in resp.cookies

    db_session.refresh(user_avec_email)
    assert verify_password("nouveau-mot-de-passe", user_avec_email.password_hash)
    assert not verify_password("ancien-mot-de-passe", user_avec_email.password_hash)


def test_lien_ne_sert_qu_une_fois(client, user_avec_email):
    """Le jeton porte l'empreinte du mot de passe : le changer l'invalide."""
    token = _reset_token(user_avec_email)
    ok = {"token": token, "password": "premier-choix", "password_confirm": "premier-choix"}
    assert client.post("/app/reinitialiser", data=ok, follow_redirects=False).status_code == 303

    rejoue = {"token": token, "password": "second-choix", "password_confirm": "second-choix"}
    assert client.post("/app/reinitialiser", data=rejoue).status_code == 400


def test_lien_expire_refuse(client, user_avec_email):
    perime = create_token(
        {"reset": user_avec_email.id, "pw": _password_fingerprint(user_avec_email)}, max_age=-1
    )
    assert client.get("/app/reinitialiser", params={"token": perime}).status_code == 400


def test_jeton_forge_refuse(client, user_avec_email):
    """Une empreinte inventée ne doit pas suffire, même avec le bon identifiant."""
    forge = create_token({"reset": user_avec_email.id, "pw": "0" * 16}, max_age=1800)
    assert client.get("/app/reinitialiser", params={"token": forge}).status_code == 400
    assert client.get("/app/reinitialiser", params={"token": "n-importe-quoi"}).status_code == 400


def test_confirmation_exigee_a_la_reinitialisation(client, db_session, user_avec_email):
    token = _reset_token(user_avec_email)
    resp = client.post(
        "/app/reinitialiser",
        data={"token": token, "password": "nouveau-mot-de-passe", "password_confirm": "faute-de-frappe"},
    )
    assert resp.status_code == 422
    db_session.refresh(user_avec_email)
    assert verify_password("ancien-mot-de-passe", user_avec_email.password_hash)


def test_demandes_plafonnees_par_adresse_ip(client, user_avec_email):
    for _ in range(3):
        assert client.post("/app/mot-de-passe-oublie", data={"identifier": "awa@test.cm"}).status_code == 200
    bloque = client.post("/app/mot-de-passe-oublie", data={"identifier": "awa@test.cm"})
    assert bloque.status_code == 429
    assert bloque.headers.get("Retry-After")


# --------------------------------------------------------------------------- #
# Connexion
# --------------------------------------------------------------------------- #
def test_connexion_plafonnee_apres_huit_essais(client, user_avec_email):
    codes = [
        client.post("/app/login", data={"identifier": "awa@test.cm", "password": f"faux{i}"},
                    follow_redirects=False).status_code
        for i in range(10)
    ]
    assert codes[:8] == [401] * 8
    assert codes[8:] == [429, 429]


# --------------------------------------------------------------------------- #
# Routes qui ne doivent plus exister
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("url", ["/init-test-shop", "/add-test-images"])
def test_routes_de_test_supprimees(client, url):
    """Elles écrivaient en base sans aucune authentification."""
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("method,url", [
    ("GET", "/api/billing/status/1"),
    ("POST", "/api/billing/campay/initiate?shop_id=1&plan=starter&phone=237650000000"),
])
def test_routes_de_facturation_exigent_une_session(client, method, url):
    assert client.request(method, url).status_code == 401


# --------------------------------------------------------------------------- #
# Suspension automatique des abonnements échus
# --------------------------------------------------------------------------- #
def test_abonnement_echu_suspend_la_boutique(db_session, make_shop):
    from app.services import billing as billing_service

    _, shop = make_shop("Boutique Echue")
    db_session.add(models.Subscription(
        shop_id=shop.id, plan=models.SubscriptionPlan.STARTER,
        current_period_end=utcnow() - timedelta(days=10),
        auto_suspend=True, grace_days=3,
    ))
    db_session.commit()

    assert billing_service.enforce_all(db_session) == [shop.id]
    db_session.refresh(shop)
    assert shop.status == models.ShopStatus.SUSPENDED

    # Idempotent : un second passage ne resuspend pas.
    assert billing_service.enforce_all(db_session) == []


def test_abonnement_dans_le_delai_de_grace_reste_actif(db_session, make_shop):
    from app.services import billing as billing_service

    _, shop = make_shop("Boutique Grace")
    db_session.add(models.Subscription(
        shop_id=shop.id, plan=models.SubscriptionPlan.STARTER,
        current_period_end=utcnow() - timedelta(days=1),
        auto_suspend=True, grace_days=7,
    ))
    db_session.commit()

    assert billing_service.enforce_all(db_session) == []
    db_session.refresh(shop)
    assert shop.status == models.ShopStatus.ACTIVE
