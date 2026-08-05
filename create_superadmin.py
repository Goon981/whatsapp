#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password

db = SessionLocal()
admin = db.query(User).filter(User.email == "admin@shopcam.cm").first()
if admin:
    print("Admin existe deja")
    db.close()
    sys.exit(0)

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
print("Admin cree avec succes!")
print("Email: admin@shopcam.cm")
print("Password: Admin@SmartShop2024!")
db.close()
