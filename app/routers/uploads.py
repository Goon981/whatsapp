from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
import os
import uuid
from app.deps import require_shop_access

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# Créer les dossiers s'ils n'existent pas
UPLOAD_DIR = Path("static/uploads")
PRODUCT_DIR = UPLOAD_DIR / "products"
SHOP_DIR = UPLOAD_DIR / "shops"

PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
SHOP_DIR.mkdir(parents=True, exist_ok=True)

# Extensions autorisées
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def validate_image(file: UploadFile) -> bool:
    """Valide le fichier image"""
    if file.content_type not in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
        raise HTTPException(status_code=400, detail="Format d'image non autorisé")

    # Vérifier l'extension
    ext = file.filename.split('.')[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extension non autorisée")

    return True


@router.post("/product-image")
async def upload_product_image(file: UploadFile = File(...), shop_id: int = Depends(require_shop_access)):
    """Upload une image de produit"""

    try:
        validate_image(file)

        # Générer un nom unique
        file_ext = file.filename.split('.')[-1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        filepath = PRODUCT_DIR / unique_filename

        # Sauvegarder le fichier
        with open(filepath, "wb") as f:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 5MB)")
            f.write(content)

        # Retourner l'URL publique
        return {
            "success": True,
            "url": f"/static/uploads/products/{unique_filename}",
            "filename": unique_filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shop-logo")
async def upload_shop_logo(file: UploadFile = File(...), shop_id: int = Depends(require_shop_access)):
    """Upload le logo d'une boutique"""

    try:
        validate_image(file)

        # Utiliser shop_id comme nom
        file_ext = file.filename.split('.')[-1].lower()
        filename = f"shop_{shop_id}.{file_ext}"
        filepath = SHOP_DIR / filename

        # Sauvegarder
        with open(filepath, "wb") as f:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="Fichier trop volumineux")
            f.write(content)

        return {
            "success": True,
            "url": f"/static/uploads/shops/{filename}",
            "filename": filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
