"""Envoi d'e-mails transactionnels (réinitialisation de mot de passe).

Repose sur ``smtplib`` de la bibliothèque standard : aucune dépendance ni
service tiers à souscrire. Tant que ``SMARTSHOP_SMTP_HOST`` n'est pas défini,
``send`` renvoie ``False`` sans rien tenter — l'appelant sait alors que le
message n'est pas parti et le dit à l'utilisateur, plutôt que d'afficher un
« e-mail envoyé » mensonger.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from ..config import settings

logger = logging.getLogger("smartshop")

TIMEOUT = 15


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def send(to: str, subject: str, body: str) -> bool:
    """Envoie un message. Retourne ``False`` si l'envoi n'a pas abouti."""
    if not is_configured():
        logger.warning("SMTP non configuré : e-mail « %s » non envoyé à %s.", subject, to)
        return False

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT,
                timeout=TIMEOUT, context=ssl.create_default_context(),
            )
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=TIMEOUT)
        with server:
            if settings.SMTP_PORT != 465 and settings.SMTP_TLS:
                server.starttls(context=ssl.create_default_context())
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # L'adresse du destinataire n'est pas journalisée avec l'erreur : les
        # journaux d'hébergement sont lisibles par plus de monde que la boîte.
        logger.error("Échec d'envoi SMTP (%s) : %s", subject, exc)
        return False

    logger.info("E-mail « %s » envoyé.", subject)
    return True
