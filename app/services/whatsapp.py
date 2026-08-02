"""Génération du message WhatsApp structuré et du lien pré-rempli (§6.6).

MVP : on construit un lien ``https://wa.me/<numero>?text=<message>`` que le client
ouvre pour transmettre le récapitulatif au commerçant. L'API WhatsApp Business
(notifications automatiques) est prévue pour une phase ultérieure. Dans tous les cas,
la commande reste enregistrée dans SmartShop même si l'envoi échoue (RM-10).
"""
from __future__ import annotations

import urllib.parse

from .. import models
from .pricing import format_fcfa


def _clean_number(number: str | None) -> str:
    """Ne conserve que les chiffres (format international attendu par wa.me)."""
    if not number:
        return ""
    return "".join(ch for ch in number if ch.isdigit())


def build_order_message(shop: models.Shop, order: models.Order) -> str:
    """Compose le texte récapitulatif : référence, produits, quantités, montant, client, livraison."""
    lines: list[str] = []
    lines.append(f"*Nouvelle commande {shop.name}*")
    lines.append(f"Réf : {order.reference}")
    lines.append("")
    lines.append("*Produits*")
    for item in order.items:
        label = item.product_name
        if item.variant_name:
            label += f" — {item.variant_name}"
        lines.append(f"• {label} x{item.quantity} = {format_fcfa(item.line_total)}")
    lines.append("")
    lines.append(f"Sous-total : {format_fcfa(order.subtotal)}")
    if order.delivery_fee:
        lines.append(f"Livraison : {format_fcfa(order.delivery_fee)}")
    if order.discount:
        lines.append(f"Remise : -{format_fcfa(order.discount)}")
    lines.append(f"*Total : {format_fcfa(order.total)}*")
    lines.append("")
    lines.append("*Client*")
    lines.append(f"Nom : {order.customer_name}")
    lines.append(f"Téléphone : {order.customer_phone}")
    if order.is_pickup:
        lines.append("Retrait en boutique")
    else:
        loc = ", ".join(
            part for part in [order.delivery_city, order.delivery_district, order.delivery_details] if part
        )
        lines.append(f"Livraison : {loc or 'à préciser'}")
    method_labels = {
        models.PaymentMethod.MTN_MOMO: "MTN MoMo",
        models.PaymentMethod.ORANGE_MONEY: "Orange Money",
        models.PaymentMethod.CASH_ON_DELIVERY: "Paiement à la livraison",
    }
    lines.append(f"Paiement : {method_labels.get(order.payment_method, order.payment_method.value)}")
    if order.customer_note:
        lines.append("")
        lines.append(f"Note : {order.customer_note}")
    return "\n".join(lines)


def build_wa_link(shop: models.Shop, order: models.Order) -> str:
    """Construit le lien wa.me pré-rempli vers le numéro WhatsApp de la boutique."""
    number = _clean_number(shop.whatsapp_number or shop.contact_phone)
    text = urllib.parse.quote(build_order_message(shop, order))
    if number:
        return f"https://wa.me/{number}?text={text}"
    # Sans numéro configuré : lien générique que le client dirige lui-même.
    return f"https://wa.me/?text={text}"
