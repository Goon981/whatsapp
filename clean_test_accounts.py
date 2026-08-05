#!/usr/bin/env python3
"""Script pour supprimer tous les comptes de test créés"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import User, Shop

def delete_all_test_accounts():
    """Supprime tous les comptes de test"""
    db = SessionLocal()

    try:
        # Récupérer tous les utilisateurs
        users = db.query(User).all()
        shops = db.query(Shop).all()

        print(f"Utilisateurs trouvés: {len(users)}")
        print(f"Boutiques trouvées: {len(shops)}")

        if len(users) == 0:
            print("\nAucun compte à supprimer.")
            return

        print("\n--- COMPTES À SUPPRIMER ---\n")
        for user in users:
            print(f"  - {user.full_name} ({user.email or user.phone})")

        # Demander confirmation
        confirm = input("\n⚠️  Êtes-vous SÛR de vouloir SUPPRIMER TOUS CES COMPTES ? (oui/non): ").strip().lower()

        if confirm != "oui":
            print("Annulé.")
            return

        # Supprimer les boutiques d'abord (cascade)
        for shop in shops:
            db.delete(shop)
            print(f"✓ Supprimé boutique: {shop.name}")

        # Supprimer les utilisateurs
        for user in users:
            db.delete(user)
            print(f"✓ Supprimé utilisateur: {user.email or user.phone}")

        db.commit()
        print(f"\n✅ {len(users)} compte(s) supprimé(s) avec succès!")
        print(f"✅ {len(shops)} boutique(s) supprimée(s) avec succès!")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("SUPPRESSION DES COMPTES DE TEST")
    print("=" * 50)
    print()

    delete_all_test_accounts()
