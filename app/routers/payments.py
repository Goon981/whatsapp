"""API paiements (§13, §6.7) : initialisation, webhook signé idempotent, remboursement.

La confirmation d'un paiement repose EXCLUSIVEMENT sur le webhook signé côté serveur
(RM-07, §6.7). Aucun endpoint ne permet au client de déclarer lui-même un paiement réussi.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_permission
from ..security import verify_signature
from ..services import orders as orders_service
from ..services.orders import OrderError

router = APIRouter(tags=["payments"])


@router.post("/api/payments/webhook")
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> dict:
    """Reçoit un évènement de l'agrégateur. Vérifie la signature HMAC du corps brut.

    Idempotent : un ``event_id`` déjà vu renvoie 200 sans double effet (RM-07).
    """
    raw = await request.body()
    if not verify_signature(raw, x_signature or ""):
        raise HTTPException(401, "Signature de webhook invalide.")

    try:
        data = schemas.PaymentWebhookIn.model_validate_json(raw)
    except Exception:  # noqa: BLE001 - payload malformé
        raise HTTPException(422, "Payload de webhook invalide.")

    try:
        payment = orders_service.apply_payment_event(
            db,
            event_id=data.event_id,
            provider="aggregator",
            payment_reference=data.payment_reference,
            new_status=data.status,
            payload=data.model_dump(),
        )
    except OrderError as exc:
        if str(exc) == "duplicate_event":
            # Doublon : accusé de réception sans réappliquer (idempotence).
            return {"status": "ignored", "reason": "duplicate_event"}
        raise HTTPException(404, str(exc))

    return {"status": "ok", "payment_status": payment.status.value}


@router.post("/api/shops/{shop_id}/payments/{payment_id}/refund")
def refund(
    payment_id: int,
    access=Depends(require_permission("orders")),
    db: Session = Depends(get_db),
) -> dict:
    shop, _ = access
    payment = (
        db.query(models.Payment)
        .filter(models.Payment.id == payment_id, models.Payment.shop_id == shop.id)
        .first()
    )
    if payment is None:
        raise HTTPException(404, "Paiement introuvable.")
    try:
        payment = orders_service.refund_payment(db, payment, actor="commerçant")
    except OrderError as exc:
        raise HTTPException(409, str(exc))
    return {"status": payment.status.value, "order_id": payment.order_id}
