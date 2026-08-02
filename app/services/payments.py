"""Abstraction de paiement Mobile Money (§6.7, risque « multi-fournisseurs »).

Le MVP fournit un agrégateur *simulé* : il crée une transaction en attente puis,
après confirmation serveur (webhook signé), la marque réussie/échouée. Aucune
validation ne repose sur l'écran du client (RM/§6.7) ; aucun code PIN n'est stocké.

Pour brancher un agrégateur réel (compatible Cameroun), il suffit d'implémenter la
même interface ``PaymentProvider`` et de l'enregistrer dans ``get_provider``.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import models
from ..security import new_reference


@dataclass
class InitResult:
    reference: str
    provider_reference: str
    status: models.PaymentStatus
    instructions: str


class PaymentProvider:
    """Interface commune à tous les fournisseurs de paiement."""

    name: str = "base"

    def initialize(self, order: models.Order, method: models.PaymentMethod) -> InitResult:  # noqa: D401
        raise NotImplementedError


class SimulatedMomoProvider(PaymentProvider):
    """Agrégateur simulé pour la démo (MTN MoMo / Orange Money)."""

    name = "simulated_momo"

    def initialize(self, order: models.Order, method: models.PaymentMethod) -> InitResult:
        provider_ref = new_reference("PSP")
        label = "MTN MoMo" if method == models.PaymentMethod.MTN_MOMO else "Orange Money"
        instructions = (
            f"Une demande de paiement {label} de {order.total} FCFA a été initiée. "
            "Confirmez sur votre téléphone. La commande sera validée après confirmation serveur."
        )
        return InitResult(
            reference=new_reference("PAY"),
            provider_reference=provider_ref,
            status=models.PaymentStatus.PENDING,
            instructions=instructions,
        )


_PROVIDERS: dict[str, PaymentProvider] = {
    SimulatedMomoProvider.name: SimulatedMomoProvider(),
}


def get_provider(name: str = SimulatedMomoProvider.name) -> PaymentProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Fournisseur de paiement inconnu : {name}")
    return provider


def method_to_provider(method: models.PaymentMethod) -> str:
    """Le MVP route MTN et Orange vers le même agrégateur simulé."""
    return SimulatedMomoProvider.name
