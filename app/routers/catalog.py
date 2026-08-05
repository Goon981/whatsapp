"""API catalogue (§13) : catégories, produits, variantes, stock.

Toutes les requêtes sont filtrées par ``shop_id`` (RM-05). Les suppressions sont
logiques (archivage — RM-09).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pathlib import Path
import os
import uuid

from .. import models, schemas
from ..database import get_db
from ..deps import require_permission, require_shop_access
from ..config import settings

router = APIRouter(prefix="/api/shops/{shop_id}", tags=["catalog"])


# --------------------------------------------------------------------------- #
# Catégories
# --------------------------------------------------------------------------- #
@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(access=Depends(require_shop_access), db: Session = Depends(get_db)):
    shop, _ = access
    return (
        db.query(models.Category)
        .filter(models.Category.shop_id == shop.id)
        .order_by(models.Category.position)
        .all()
    )


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(
    data: schemas.CategoryIn,
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
):
    shop, _ = access
    cat = models.Category(shop_id=shop.id, name=data.name, position=data.position)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# --------------------------------------------------------------------------- #
# Produits
# --------------------------------------------------------------------------- #
def _get_owned_product(db: Session, shop_id: int, product_id: int) -> models.Product:
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop_id)
        .first()
    )
    if product is None:
        raise HTTPException(404, "Produit introuvable.")
    return product


@router.get("/products", response_model=list[schemas.ProductOut])
def list_products(
    access=Depends(require_shop_access),
    db: Session = Depends(get_db),
    include_archived: bool = False,
):
    shop, _ = access
    query = db.query(models.Product).filter(models.Product.shop_id == shop.id)
    if not include_archived:
        query = query.filter(models.Product.is_archived.is_(False))
    return query.order_by(models.Product.created_at.desc()).all()


@router.post("/products", response_model=schemas.ProductOut, status_code=201)
def create_product(
    data: schemas.ProductIn,
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
):
    shop, _ = access
    if data.category_id is not None:
        cat = (
            db.query(models.Category)
            .filter(models.Category.id == data.category_id, models.Category.shop_id == shop.id)
            .first()
        )
        if cat is None:
            raise HTTPException(422, "Catégorie invalide pour cette boutique.")

    product = models.Product(
        shop_id=shop.id,
        category_id=data.category_id,
        name=data.name,
        description=data.description,
        image_url=data.image_url,
        price=data.price,
        promo_price=data.promo_price,
        sku=data.sku,
        stock=data.stock,
        low_stock_threshold=data.low_stock_threshold,
        status=data.status,
    )
    db.add(product)
    db.flush()
    for v in data.variants:
        db.add(
            models.ProductVariant(
                shop_id=shop.id,
                product_id=product.id,
                name=v.name,
                sku=v.sku,
                price=v.price,
                stock=v.stock,
            )
        )
    db.commit()
    db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, access=Depends(require_shop_access), db: Session = Depends(get_db)):
    shop, _ = access
    return _get_owned_product(db, shop.id, product_id)


@router.patch("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    data: schemas.ProductIn,
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
):
    shop, _ = access
    product = _get_owned_product(db, shop.id, product_id)
    payload = data.model_dump(exclude={"variants"})
    for field, value in payload.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.post("/products/{product_id}/archive", status_code=200)
def archive_product(
    product_id: int,
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
) -> dict:
    """Suppression logique du produit (RM-09)."""
    shop, _ = access
    product = _get_owned_product(db, shop.id, product_id)
    product.is_archived = True
    db.commit()
    return {"archived": True, "product_id": product_id}


@router.post("/products/{product_id}/duplicate", response_model=schemas.ProductOut, status_code=201)
def duplicate_product(
    product_id: int,
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
):
    shop, _ = access
    src = _get_owned_product(db, shop.id, product_id)
    copy = models.Product(
        shop_id=shop.id,
        category_id=src.category_id,
        name=f"{src.name} (copie)",
        description=src.description,
        image_url=src.image_url,
        price=src.price,
        promo_price=src.promo_price,
        stock=src.stock,
        low_stock_threshold=src.low_stock_threshold,
        status=models.ProductStatus.HIDDEN,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy


# --------------------------------------------------------------------------- #
# Galerie d'images des produits
# --------------------------------------------------------------------------- #
class ProductImageIn(schemas.BaseModel):
    alt_text: str | None = None


@router.get("/products/{product_id}/images", response_model=list[schemas.ProductImageOut])
def list_product_images(
    product_id: int,
    access=Depends(require_shop_access),
    db: Session = Depends(get_db),
):
    """Récupère toutes les images d'un produit."""
    shop, _ = access
    product = _get_owned_product(db, shop.id, product_id)
    return (
        db.query(models.ProductImage)
        .filter(models.ProductImage.product_id == product_id)
        .order_by(models.ProductImage.position)
        .all()
    )


@router.post("/products/{product_id}/images", response_model=schemas.ProductImageOut, status_code=201)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
):
    """Upload une image pour la galerie du produit."""
    shop, _ = access
    product = _get_owned_product(db, shop.id, product_id)

    # Validation du fichier
    if file.content_type not in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
        raise HTTPException(status_code=400, detail="Format d'image non autorisé")

    ext = file.filename.split('.')[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
        raise HTTPException(status_code=400, detail="Extension non autorisée")

    # Sauvegarder l'image
    upload_dir = settings.STATIC_DIR / "uploads" / "products"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}.{ext}"
    filepath = upload_dir / filename

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 5MB)")

    with open(filepath, "wb") as f:
        f.write(content)

    # Créer l'entry ProductImage
    max_position = (
        db.query(db.func.max(models.ProductImage.position))
        .filter(models.ProductImage.product_id == product_id)
        .scalar()
    ) or 0

    image = models.ProductImage(
        shop_id=shop.id,
        product_id=product_id,
        image_url=f"/static/uploads/products/{filename}",
        position=max_position + 1,
        is_primary=False,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


@router.delete("/products/{product_id}/images/{image_id}", status_code=200)
def delete_product_image(
    product_id: int,
    image_id: int,
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
) -> dict:
    """Supprime une image de la galerie."""
    shop, _ = access
    _get_owned_product(db, shop.id, product_id)

    image = (
        db.query(models.ProductImage)
        .filter(
            models.ProductImage.id == image_id,
            models.ProductImage.product_id == product_id,
            models.ProductImage.shop_id == shop.id,
        )
        .first()
    )
    if image is None:
        raise HTTPException(404, "Image introuvable.")

    # Supprimer le fichier physique
    if image.image_url.startswith("/static/uploads/products/"):
        filename = image.image_url.split("/")[-1]
        filepath = settings.STATIC_DIR / "uploads" / "products" / filename
        if filepath.exists():
            os.remove(filepath)

    db.delete(image)
    db.commit()
    return {"deleted": True, "image_id": image_id}


@router.put("/products/{product_id}/images/{image_id}/primary", status_code=200)
def set_primary_image(
    product_id: int,
    image_id: int,
    access=Depends(require_permission("catalog")),
    db: Session = Depends(get_db),
) -> dict:
    """Définit une image comme image principale du produit."""
    shop, _ = access
    product = _get_owned_product(db, shop.id, product_id)

    image = (
        db.query(models.ProductImage)
        .filter(
            models.ProductImage.id == image_id,
            models.ProductImage.product_id == product_id,
        )
        .first()
    )
    if image is None:
        raise HTTPException(404, "Image introuvable.")

    # Retirer le is_primary des autres images
    db.query(models.ProductImage).filter(
        models.ProductImage.product_id == product_id,
        models.ProductImage.id != image_id,
    ).update({models.ProductImage.is_primary: False})

    # Définir comme primaire
    image.is_primary = True
    product.image_url = image.image_url  # Mettre à jour l'image principale du produit

    db.commit()
    return {"primary": True, "image_id": image_id}
