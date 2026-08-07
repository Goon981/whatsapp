from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
import os
import uuid
from app.deps import get_current_user
from app.database import get_db
from app import models
from app.config import settings
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# Créer les dossiers s'ils n'existent pas
UPLOAD_DIR = settings.STATIC_DIR / "uploads"
PRODUCT_DIR = UPLOAD_DIR / "products"
SHOP_DIR = UPLOAD_DIR / "shops"

PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
SHOP_DIR.mkdir(parents=True, exist_ok=True)

# Extensions autorisées
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def validate_image(file: UploadFile) -> str:
    """Valide le fichier image et retourne son extension normalisée."""
    if file.content_type not in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
        raise HTTPException(status_code=400, detail="Format d'image non autorisé")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extension non autorisée")

    return ext


async def _read_within_limit(file: UploadFile) -> bytes:
    """Lit le fichier en refusant tout dépassement de taille.

    La lecture est bornée et effectuée avant toute écriture : contrôler la
    taille après ``open()`` laissait un fichier vide sur le disque à chaque
    envoi refusé, et lire sans borne exposait la mémoire du serveur.
    """
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 5 Mo)")
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")
    return content


def _user_shop(db: Session, user: models.User) -> models.Shop:
    """Boutique du commerçant, en incluant celles où il est membre."""
    shop = (
        db.query(models.Shop)
        .outerjoin(models.ShopMember, models.ShopMember.shop_id == models.Shop.id)
        .filter(
            models.Shop.is_deleted.is_(False),
            (models.Shop.owner_id == user.id) | (models.ShopMember.user_id == user.id),
        )
        .first()
    )
    if not shop:
        raise HTTPException(status_code=404, detail="Boutique non trouvée")
    return shop


@router.post("/product-image")
async def upload_product_image(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload une image de produit"""

    file_ext = validate_image(file)
    _user_shop(db, user)
    content = await _read_within_limit(file)

    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    (PRODUCT_DIR / unique_filename).write_bytes(content)

    return {
        "success": True,
        "url": f"/static/uploads/products/{unique_filename}",
        "filename": unique_filename,
    }


@router.post("/shop-logo")
async def upload_shop_logo(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload le logo d'une boutique"""

    file_ext = validate_image(file)
    shop = _user_shop(db, user)
    content = await _read_within_limit(file)

    # Nom unique : réutiliser « shop_<id>.<ext> » laissait l'ancien logo en place
    # lors d'un changement d'extension, et le cache servait la mauvaise image.
    filename = f"shop_{shop.id}_{uuid.uuid4().hex[:8]}.{file_ext}"
    (SHOP_DIR / filename).write_bytes(content)

    return {
        "success": True,
        "url": f"/static/uploads/shops/{filename}",
        "filename": filename,
    }
