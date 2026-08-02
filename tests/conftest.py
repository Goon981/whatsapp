"""Fixtures de test : base SQLite en mémoire isolée + client FastAPI."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SMARTSHOP_SECRET_KEY", "test-secret")
os.environ.setdefault("SMARTSHOP_PAYMENT_WEBHOOK_SECRET", "test-webhook-secret")

from app import database, models  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # une seule connexion partagée entre threads (TestClient)
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()

    # Redirige la dépendance get_db de l'app vers cette session.
    def _override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    return TestClient(app)


@pytest.fixture()
def make_shop(db_session):
    """Fabrique un propriétaire + boutique active prête à vendre."""
    def _make(name="Boutique Test", **shop_kwargs):
        owner = models.User(
            full_name=f"Owner {name}",
            email=f"owner-{name.lower().replace(' ', '')}@test.cm",
            password_hash=hash_password("password123"),
            role=models.UserRole.OWNER,
        )
        db_session.add(owner)
        db_session.flush()
        shop = models.Shop(
            owner_id=owner.id,
            name=name,
            slug=name.lower().replace(" ", "-"),
            whatsapp_number="+237690000000",
            status=models.ShopStatus.ACTIVE,
            **shop_kwargs,
        )
        db_session.add(shop)
        db_session.flush()
        db_session.add(models.ShopMember(
            shop_id=shop.id, user_id=owner.id, role=models.UserRole.OWNER,
            permissions={k: True for k in ["orders", "catalog", "stock", "settings", "customers", "stats"]},
        ))
        db_session.commit()
        return owner, shop

    return _make


@pytest.fixture()
def make_product(db_session):
    def _make(shop, name="Produit", price=1000, stock=10, **kwargs):
        p = models.Product(
            shop_id=shop.id, name=name, price=price, stock=stock, **kwargs
        )
        db_session.add(p)
        db_session.commit()
        return p

    return _make
