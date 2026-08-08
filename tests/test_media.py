"""Stockage des images en base.

Écrites sur le disque du conteneur, les photos de produits disparaissaient à
chaque déploiement : le catalogue d'un commerçant se vidait de ses vignettes
sans que rien ne le signale.
"""
from __future__ import annotations

import struct
import zlib

import pytest

from app import models
from app.services import media


def png_bytes(width: int = 8, height: int = 8) -> bytes:
    """Un PNG rouge minimal, sans dépendance de traitement d'image."""
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


@pytest.fixture()
def connecte(client, make_shop):
    owner, shop = make_shop("Boutique Media")
    client.post(
        "/app/login",
        data={"identifier": owner.email, "password": "password123"},
        follow_redirects=False,
    )
    return shop


def test_image_de_produit_stockee_en_base(client, db_session, connecte):
    resp = client.post(
        "/app/products",
        data={"name": "Produit avec photo", "price": "2500", "stock": "5"},
        files=[("files", ("photo.png", png_bytes(), "image/png"))],
        follow_redirects=False,
    )
    assert resp.status_code == 303

    image = db_session.query(models.ProductImage).one()
    assert image.image_url.startswith("/media/")

    blob = db_session.get(models.MediaFile, media.media_id(image.image_url))
    assert blob is not None
    assert blob.content_type == "image/png"
    assert blob.shop_id == connecte.id
    assert blob.size == len(png_bytes())


def test_image_servie_avec_un_cache_permanent(client, db_session, connecte):
    client.post(
        "/app/products",
        data={"name": "Produit", "price": "1000"},
        files=[("files", ("photo.png", png_bytes(), "image/png"))],
        follow_redirects=False,
    )
    url = db_session.query(models.ProductImage).one().image_url

    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    # L'identifiant est unique et le contenu ne change jamais.
    assert "immutable" in resp.headers["cache-control"]
    assert resp.content == png_bytes()


def test_image_inconnue_renvoie_404(client):
    assert client.get("/media/identifiant-inexistant").status_code == 404


def test_fichier_trop_volumineux_refuse(client, db_session, connecte):
    """La lecture est bornée : sans cela, tout l'envoi passait en mémoire."""
    enorme = b"\x89PNG\r\n\x1a\n" + b"0" * (media.MAX_FILE_SIZE + 1024)
    resp = client.post(
        "/app/products",
        data={"name": "Trop lourd", "price": "1000"},
        files=[("files", ("gros.png", enorme, "image/png"))],
        follow_redirects=False,
    )
    assert resp.status_code == 413
    assert db_session.query(models.MediaFile).count() == 0


def test_format_non_image_ignore(client, db_session, connecte):
    resp = client.post(
        "/app/products",
        data={"name": "Produit", "price": "1000"},
        files=[("files", ("script.pdf", b"%PDF-1.4 ...", "application/pdf"))],
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert db_session.query(models.MediaFile).count() == 0
    assert db_session.query(models.ProductImage).count() == 0


def test_suppression_libere_les_octets(client, db_session, connecte):
    """Sans cela la base conserve indéfiniment des images que rien ne référence."""
    url = media.store(db_session, png_bytes(), "image/png", shop_id=connecte.id)
    db_session.commit()
    assert db_session.query(models.MediaFile).count() == 1

    media.delete(db_session, url)
    db_session.commit()
    assert db_session.query(models.MediaFile).count() == 0


def test_suppression_ignore_les_anciennes_urls(db_session):
    """Les quelques fichiers versionnés dans le dépôt gardent leur URL /static."""
    media.delete(db_session, "/static/uploads/products/ancienne.jpg")  # ne doit pas lever
    assert media.media_id("/static/uploads/products/ancienne.jpg") is None
