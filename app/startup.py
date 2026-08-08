"""Tâches exécutées au démarrage et en arrière-plan.

Deux besoins que l'hébergement ne couvre pas :

- la clé de signature des sessions doit survivre au renouvellement du mot de
  passe PostgreSQL, dont elle était dérivée faute de mieux ;
- les abonnements échus doivent être suspendus. La route prévue pour cela
  existe et est protégée par un secret, mais aucune tâche planifiée ne
  l'appelait : un essai expiré ne se fermait donc jamais.
"""
from __future__ import annotations

import asyncio
import logging
import secrets

from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .database import SessionLocal
from .models import AppSetting
from .security import install_signing_key

logger = logging.getLogger("smartshop")

SIGNING_KEY_NAME = "session_signing_key"

# Une vérification par heure : l'échéance se compte en jours, inutile de
# solliciter la base plus souvent.
ENFORCE_INTERVAL = 3600


def load_signing_key() -> None:
    """Charge la clé de signature, en la créant à la première exécution.

    ``SMARTSHOP_SECRET_KEY`` reste prioritaire : un opérateur qui fixe sa clé
    explicitement doit rester maître de la rotation.
    """
    explicit = (settings.SECRET_KEY or "").strip()
    if explicit and not settings.IS_PRODUCTION:
        return  # développement : la valeur par défaut du dépôt suffit.

    db = SessionLocal()
    try:
        row = db.get(AppSetting, SIGNING_KEY_NAME)
        if row is None:
            row = AppSetting(key=SIGNING_KEY_NAME, value=secrets.token_urlsafe(48))
            db.add(row)
            db.commit()
            logger.info("Clé de signature des sessions créée et enregistrée.")
        install_signing_key(row.value)
    except SQLAlchemyError as exc:
        # Sans clé persistante on garde celle de l'environnement : les sessions
        # ne survivront pas au redémarrage, mais le site démarre.
        logger.error("Clé de signature illisible en base (%s) : repli sur l'environnement.", exc)
    finally:
        db.close()


async def enforce_subscriptions_loop() -> None:
    """Suspend périodiquement les boutiques dont l'abonnement est échu."""
    from .services import billing as billing_service

    while True:
        try:
            await asyncio.sleep(ENFORCE_INTERVAL)
            db = SessionLocal()
            try:
                suspended = billing_service.enforce_all(db)
                if suspended:
                    logger.info("Abonnements échus : %d boutique(s) suspendue(s).", len(suspended))
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - la boucle ne doit jamais s'arrêter
            logger.exception("Échec de la vérification des abonnements ; reprise au prochain tour.")
