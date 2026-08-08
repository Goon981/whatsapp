"""Envoi d'images (photos de produits, logo de boutique).

Les fichiers sont conservés en base via ``services.media`` : écrits sur le
disque du conteneur, ils disparaissaient à chaque déploiement.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.deps import get_current_user
from app.services import media

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _user_shop(db: Session, user: models.User) -> models.Shop:
    """Boutique du commerçant, en incluant celles où il est simple membre."""
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
    db: Session = Depends(get_db),
):
    """Enregistre une image de produit et retourne son URL."""
    shop = _user_shop(db, user)
    url = await media.store_upload(db, file, shop_id=shop.id)
    db.commit()
    return {"success": True, "url": url}


@router.post("/shop-logo")
async def upload_shop_logo(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enregistre le logo de la boutique et retourne son URL."""
    shop = _user_shop(db, user)
    previous = shop.logo_url
    url = await media.store_upload(db, file, shop_id=shop.id)
    shop.logo_url = url
    # L'ancien logo n'est plus référencé : le conserver ferait grossir la base
    # à chaque changement.
    media.delete(db, previous)
    db.commit()
    return {"success": True, "url": url}
