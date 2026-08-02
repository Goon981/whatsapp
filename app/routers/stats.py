"""API statistiques (§13) : agrégats par période et boutique."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_permission
from ..services import stats as stats_service

router = APIRouter(prefix="/api/shops/{shop_id}", tags=["stats"])


@router.get("/stats")
def shop_stats(access=Depends(require_permission("stats")), db: Session = Depends(get_db)) -> dict:
    shop, _ = access
    return stats_service.shop_dashboard(db, shop.id)
