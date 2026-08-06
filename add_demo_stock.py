#!/usr/bin/env python
"""Ajouter du stock aux produits de la boutique de démo 'dorian' en production."""
from app.database import SessionLocal
from app import models

db = SessionLocal()
try:
    # Chercher la boutique "dorian"
    shop = db.query(models.Shop).filter(models.Shop.slug == "dorian").first()
    if not shop:
        print("❌ Boutique 'dorian' non trouvée")
    else:
        print(f"✓ Boutique trouvée: {shop.name} (ID: {shop.id})")

        # Ajouter du stock à tous les produits
        products = db.query(models.Product).filter(models.Product.shop_id == shop.id).all()
        for p in products:
            old_stock = p.stock
            p.stock = 50  # Ajouter 50 unités de stock
            db.add(p)
            print(f"  ✓ {p.name}: {old_stock} → {p.stock} unités")

        # S'assurer que la boutique accepte tous les moyens de paiement
        shop.accept_mtn_momo = True
        shop.accept_orange_money = True
        shop.accept_airtel_money = True
        shop.accept_card = True
        shop.accept_cash_on_delivery = True
        db.add(shop)
        print(f"✓ Moyens de paiement activés pour la boutique")

        db.commit()
        print("\n✅ Stock ajouté avec succès!")
finally:
    db.close()
