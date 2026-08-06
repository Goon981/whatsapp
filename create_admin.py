#!/usr/bin/env python
from app.database import SessionLocal
from app import models
from app.security import hash_password

db = SessionLocal()

# Vérifier si admin existe déjà
admin = db.query(models.User).filter(models.User.email == "admin@smartshop.cm").first()

if admin:
    print("✓ Super Admin existe déjà")
    print(f"  Email: {admin.email}")
    print(f"  Role: {admin.role.value}")
else:
    # Créer le super admin
    admin_user = models.User(
        full_name="Super Admin SmartShop",
        email="admin@smartshop.cm",
        phone="+237677777777",
        password_hash=hash_password("AdminSmartShop2026!"),
        role=models.UserRole.SUPERADMIN,
        is_active=True,
        phone_verified=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    print("✓ Super Admin créé avec succès!")
    print(f"  Email: {admin_user.email}")
    print(f"  Role: {admin_user.role.value}")

print("\n📋 IDENTIFIANTS DE CONNEXION:")
print("─" * 50)
print("Email/Téléphone: admin@smartshop.cm")
print("Mot de passe:    AdminSmartShop2026!")
print("─" * 50)
print("\n🔗 Lien de connexion: http://localhost:8000/app/login")

db.close()
