"""Endpoint de setup initial (créer superadmin)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
from app.services.auth import hash_password

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.post("/create-superadmin")
async def create_superadmin(db: Session = Depends(get_db)):
    """Créer le compte superadmin.

    ⚠️ À exécuter UNE SEULE FOIS après déploiement.
    """

    # Vérifier si superadmin existe
    admin = db.query(User).filter(User.email == "admin@shopcam.cm").first()
    if admin:
        return {
            "success": False,
            "message": "Superadmin existe déjà",
            "email": admin.email
        }

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

    return {
        "success": True,
        "message": "✅ Superadmin créé avec succès",
        "credentials": {
            "email": "admin@shopcam.cm",
            "password": "Admin@SmartShop2024!",
            "role": admin.role,
            "access_url": "https://shopcam237.com/admin"
        }
    }
