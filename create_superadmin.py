#!/usr/bin/env python3
"""Script pour créer le compte superadmin."""

import sys
from pathlib import Path

# Ajouter app au chemin
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import User, UserRole
from app.services.auth import hash_password

db = SessionLocal()

# Vérifier si superadmin existe déjà
admin = db.query(User).filter(User.email == "admin@shopcam.cm").first()
if admin:
    print("✅ Admin existe déjà")
    print(f"Email: {admin.email}")
    print(f"Rôle: {admin.role}")
    db.close()
    sys.exit(0)

# Créer le superadmin
admin = User(
    full_name="SmartShop Admin",
    email="admin@shopcam.cm",
    phone="+237670000000",
    password_hash=hash_password("Admin@SmartShop2024!"),
    role=UserRole.SUPERADMIN,
    is_active=True,
    phone_verified=True
)

db.add(admin)
db.commit()
db.refresh(admin)

print("✅ Superadmin créé avec succès !")
print(f"\nEmail: admin@shopcam.cm")
print(f"Password: Admin@SmartShop2024!")
print(f"\nRôle: {admin.role}")
print(f"ID: {admin.id}")

db.close()
