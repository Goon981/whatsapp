"""Stockage des images téléversées.

Les fichiers vont en base (``media_files``) et non sur le disque : celui d'un
conteneur est recréé à chaque déploiement, ce qui effaçait les photos de
produits envoyées par les commerçants.

Les URL déjà enregistrées sous ``/static/uploads/...`` continuent d'être
servies : elles pointent vers les quelques fichiers versionnés dans le dépôt.
Les nouveaux envois prennent la forme ``/media/<uuid>``.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models

MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}

MEDIA_PREFIX = "/media/"


async def read_upload(file: UploadFile) -> bytes:
    """Lit un envoi en refusant tout dépassement de taille.

    La lecture est bornée : ``await file.read()`` sans argument chargeait le
    fichier entier en mémoire, quel que soit ce que l'appelant envoyait.
    """
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image trop volumineuse (max 5 Mo)")
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")
    return content


def check_type(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Format d'image non autorisé (JPG, PNG, GIF ou WebP)")
    return file.content_type


def store(db: Session, content: bytes, content_type: str, shop_id: int | None = None) -> str:
    """Enregistre une image et retourne l'URL à laquelle elle sera servie.

    Le commit est laissé à l'appelant : la ligne média et l'entité qui la
    référence doivent apparaître ensemble, sinon un échec entre les deux
    laisserait une image orpheline ou un produit pointant vers du vide.
    """
    media = models.MediaFile(
        id=str(uuid.uuid4()),
        shop_id=shop_id,
        content_type=content_type,
        size=len(content),
        data=content,
    )
    db.add(media)
    return f"{MEDIA_PREFIX}{media.id}"


async def store_upload(db: Session, file: UploadFile, shop_id: int | None = None) -> str:
    """Valide puis enregistre un envoi ; retourne son URL."""
    content_type = check_type(file)
    content = await read_upload(file)
    return store(db, content, content_type, shop_id)


def media_id(url: str | None) -> str | None:
    """Identifiant porté par une URL ``/media/<uuid>``, sinon ``None``."""
    if url and url.startswith(MEDIA_PREFIX):
        return url[len(MEDIA_PREFIX):]
    return None


def delete(db: Session, url: str | None) -> None:
    """Supprime l'image désignée par une URL, si elle est stockée en base."""
    ident = media_id(url)
    if not ident:
        return
    row = db.get(models.MediaFile, ident)
    if row is not None:
        db.delete(row)
