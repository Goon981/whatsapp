"""Jeu de données de démonstration.

Usage :  python -m app.seed
Crée un super-administrateur, un commerçant, une boutique « Chez Amina » avec
catégories, produits, zones de livraison et quelques commandes. Idempotent :
relancer ne duplique pas les comptes existants.
"""
from __future__ import annotations

from datetime import timedelta

from .database import SessionLocal, init_db
from . import models
from .models import utcnow
from .security import hash_password
from .services import orders as orders_service
from .services import pricing
from .utils import unique_shop_slug

SUPERADMIN_EMAIL = "admin@smartshop.cm"
MERCHANT_EMAIL = "amina@boutique.cm"
DEMO_PASSWORD = "smartshop123"


def _get_or_create_user(db, email, **kwargs):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        return user, False
    user = models.User(email=email, password_hash=hash_password(DEMO_PASSWORD), **kwargs)
    db.add(user)
    db.flush()
    return user, True


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        # 1) Super-administrateur
        _get_or_create_user(
            db,
            SUPERADMIN_EMAIL,
            full_name="Super Admin",
            phone="+237600000000",
            role=models.UserRole.SUPERADMIN,
            phone_verified=True,
            accepted_terms_at=utcnow(),
        )

        # 2) Commerçant + boutique
        merchant, created = _get_or_create_user(
            db,
            MERCHANT_EMAIL,
            full_name="Amina Nkeng",
            phone="+237690112233",
            role=models.UserRole.OWNER,
            accepted_terms_at=utcnow(),
        )
        if not created:
            print("Données déjà présentes — rien à recréer.")
            db.commit()
            _print_credentials()
            return

        shop = models.Shop(
            owner_id=merchant.id,
            name="Chez Amina",
            slug=unique_shop_slug(db, "Chez Amina"),
            sector="restaurant",
            description="Cuisine camerounaise maison, plats et jus frais livrés à Douala.",
            whatsapp_number="+237690112233",
            contact_phone="+237690112233",
            city="Douala",
            opening_hours="Lun-Sam 9h-21h",
            theme_color="#128C7E",
            min_order_amount=1000,
            is_open=True,
        )
        db.add(shop)
        db.flush()
        db.add(models.ShopMember(
            shop_id=shop.id, user_id=merchant.id, role=models.UserRole.OWNER,
            permissions={k: True for k in ["orders", "catalog", "stock", "settings", "customers", "stats"]},
        ))
        db.add(models.Subscription(
            shop_id=shop.id, plan=models.SubscriptionPlan.STARTER,
            status=models.SubscriptionStatus.ACTIVE, current_period_end=utcnow() + timedelta(days=30),
        ))

        # Catégories
        cats = {}
        for i, name in enumerate(["Plats", "Boissons", "Desserts"]):
            c = models.Category(shop_id=shop.id, name=name, position=i)
            db.add(c)
            db.flush()
            cats[name] = c

        # Produits
        products_data = [
            ("Plats", "Ndolé complet", "Ndolé, viande et poisson, plantain.", 3000, None, 25),
            ("Plats", "Poulet DG", "Poulet, plantains mûrs, légumes.", 4500, 4000, 15),
            ("Plats", "Eru + water fufu", "Spécialité du Sud-Ouest.", 2500, None, 20),
            ("Boissons", "Jus de gingembre 50cl", "Fait maison, épicé.", 1000, None, 40),
            ("Boissons", "Folere (bissap) 50cl", "Infusion d'hibiscus.", 1000, None, 3),
            ("Desserts", "Beignets sucrés (x6)", "Moelleux, servis chauds.", 800, None, 30),
        ]
        first_product = None
        for cat_name, name, desc, price, promo, stock in products_data:
            p = models.Product(
                shop_id=shop.id, category_id=cats[cat_name].id, name=name,
                description=desc, price=price, promo_price=promo, stock=stock,
                low_stock_threshold=5,
            )
            db.add(p)
            db.flush()
            first_product = first_product or p

        # Variantes sur le Poulet DG
        poulet = db.query(models.Product).filter(
            models.Product.shop_id == shop.id, models.Product.name == "Poulet DG"
        ).first()
        db.add(models.ProductVariant(shop_id=shop.id, product_id=poulet.id, name="Portion simple", price=4000, stock=10))
        db.add(models.ProductVariant(shop_id=shop.id, product_id=poulet.id, name="Grande portion", price=6000, stock=5))

        # Zones de livraison
        for zname, fee in [("Akwa", 500), ("Bonapriso", 700), ("Bonabéri", 1000)]:
            db.add(models.DeliveryZone(shop_id=shop.id, name=zname, fee=fee, estimated_delay="30-45 min"))

        db.commit()

        # 3) Deux commandes de démonstration (via le service métier)
        db.refresh(shop)
        ndole = db.query(models.Product).filter(
            models.Product.shop_id == shop.id, models.Product.name == "Ndolé complet"
        ).first()
        zone = db.query(models.DeliveryZone).filter(models.DeliveryZone.shop_id == shop.id).first()

        priced = pricing.price_cart(
            db, shop.id,
            [{"product_id": ndole.id, "quantity": 2}, {"product_id": first_product.id, "quantity": 1}],
            delivery_zone=zone,
        )
        order = orders_service.create_order(
            db, shop, priced,
            customer_name="Jean Etoa", customer_phone="+237677889900",
            payment_method=models.PaymentMethod.CASH_ON_DELIVERY,
            delivery_zone=zone, delivery_city="Douala", delivery_district="Akwa",
        )
        orders_service.change_status(db, order, models.OrderStatus.CONFIRMED, actor="seed")

        print("Base de démonstration créée avec succès.")
        _print_credentials()
    finally:
        db.close()


def _print_credentials() -> None:
    print("\n--- Comptes de demonstration ---")
    print(f"Super-admin : {SUPERADMIN_EMAIL} / {DEMO_PASSWORD}  -> /admin")
    print(f"Commercant  : {MERCHANT_EMAIL} / {DEMO_PASSWORD}  -> /app")
    print("Boutique demo : /s/chez-amina")


if __name__ == "__main__":
    run()
