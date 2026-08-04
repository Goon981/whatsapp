"""Modèle de données (cf. §10 du cahier des charges).

Règles transverses appliquées ici :
- Tous les montants sont des entiers de FCFA (RM-08).
- Chaque entité de boutique porte ``shop_id`` pour l'isolation multi-tenant (RM-05).
- Les suppressions courantes sont logiques via ``archived_at`` / ``is_deleted`` (RM-09).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Énumérations métier
# --------------------------------------------------------------------------- #
class UserRole(str, enum.Enum):
    OWNER = "owner"          # propriétaire de boutique
    MANAGER = "manager"      # gestionnaire
    SELLER = "seller"        # vendeur / employé
    SUPERADMIN = "superadmin"  # administrateur plateforme


class ShopStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"   # RM-01 : inaccessible au public, données conservées
    PENDING = "pending"       # en attente de vérification


class ProductStatus(str, enum.Enum):
    AVAILABLE = "available"
    OUT_OF_STOCK = "out_of_stock"
    PREORDER = "preorder"
    HIDDEN = "hidden"


class OrderStatus(str, enum.Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    MTN_MOMO = "mtn_momo"
    ORANGE_MONEY = "orange_money"
    CASH_ON_DELIVERY = "cash_on_delivery"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class SubscriptionPlan(str, enum.Enum):
    TRIAL = "trial"
    STARTER = "starter"
    BUSINESS = "business"
    PREMIUM = "premium"


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class DeliveryFeeType(str, enum.Enum):
    FIXED = "fixed"
    VARIABLE = "variable"
    PICKUP = "pickup"


# --------------------------------------------------------------------------- #
# Utilisateurs & appartenance
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(160), unique=True, index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.OWNER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_terms_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    memberships: Mapped[list["ShopMember"]] = relationship(back_populates="user")
    owned_shops: Mapped[list["Shop"]] = relationship(back_populates="owner")


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    theme_color: Mapped[str] = mapped_column(String(9), default="#128C7E")
    whatsapp_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    opening_hours: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    closed_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    min_order_amount: Mapped[int] = mapped_column(Integer, default=0)  # FCFA
    accept_cash_on_delivery: Mapped[bool] = mapped_column(Boolean, default=True)
    accept_mtn_momo: Mapped[bool] = mapped_column(Boolean, default=True)
    accept_orange_money: Mapped[bool] = mapped_column(Boolean, default=True)
    # Réserver le stock à la confirmation (True) ou au paiement (False) — RM-04.
    reserve_stock_on_confirm: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ShopStatus] = mapped_column(Enum(ShopStatus), default=ShopStatus.ACTIVE)
    suspended_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="owned_shops")
    members: Mapped[list["ShopMember"]] = relationship(back_populates="shop")
    categories: Mapped[list["Category"]] = relationship(back_populates="shop")
    products: Mapped[list["Product"]] = relationship(back_populates="shop")
    delivery_zones: Mapped[list["DeliveryZone"]] = relationship(back_populates="shop")
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="shop", uselist=False
    )


class ShopMember(Base):
    __tablename__ = "shop_members"
    __table_args__ = (UniqueConstraint("shop_id", "user_id", name="uq_shop_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.SELLER)
    # Permissions fines : {"orders": true, "catalog": true, "stock": false, ...}
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    shop: Mapped["Shop"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    shop: Mapped["Shop"] = relationship(back_populates="categories")
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[int] = mapped_column(Integer)  # FCFA, prix de base
    promo_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus), default=ProductStatus.AVAILABLE
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)  # RM-09
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    shop: Mapped["Shop"] = relationship(back_populates="products")
    category: Mapped["Category | None"] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    @property
    def effective_price(self) -> int:
        """Prix appliqué : promo si présente et inférieure, sinon prix de base."""
        if self.promo_price is not None and self.promo_price < self.price:
            return self.promo_price
        return self.price

    @property
    def is_low_stock(self) -> bool:
        return self.stock <= self.low_stock_threshold


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))  # ex. "Taille M / Rouge"
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)  # override du produit
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship(back_populates="variants")


# --------------------------------------------------------------------------- #
# Clients & adresses
# --------------------------------------------------------------------------- #
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    orders_count: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[int] = mapped_column(Integer, default=0)  # FCFA
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    addresses: Mapped[list["Address"]] = relationship(back_populates="customer")


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    city: Mapped[str] = mapped_column(String(80))
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    details: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="addresses")


# --------------------------------------------------------------------------- #
# Livraison
# --------------------------------------------------------------------------- #
class DeliveryZone(Base):
    __tablename__ = "delivery_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    fee_type: Mapped[DeliveryFeeType] = mapped_column(
        Enum(DeliveryFeeType), default=DeliveryFeeType.FIXED
    )
    fee: Mapped[int] = mapped_column(Integer, default=0)  # FCFA
    estimated_delay: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    shop: Mapped["Shop"] = relationship(back_populates="delivery_zones")


# --------------------------------------------------------------------------- #
# Commandes
# --------------------------------------------------------------------------- #
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(160))
    customer_phone: Mapped[str] = mapped_column(String(40))
    delivery_city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    delivery_district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivery_details: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_zones.id"), nullable=True
    )
    is_pickup: Mapped[bool] = mapped_column(Boolean, default=False)

    subtotal: Mapped[int] = mapped_column(Integer, default=0)     # FCFA
    delivery_fee: Mapped[int] = mapped_column(Integer, default=0)  # FCFA
    discount: Mapped[int] = mapped_column(Integer, default=0)      # FCFA
    total: Mapped[int] = mapped_column(Integer, default=0)         # FCFA

    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.CASH_ON_DELIVERY
    )
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NEW)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusHistory.created_at"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")

    @property
    def is_paid(self) -> bool:
        return any(p.status == PaymentStatus.SUCCESS for p in self.payments)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(200))  # figé au moment de la commande
    variant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit_price: Mapped[int] = mapped_column(Integer)  # FCFA, figé
    quantity: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[int] = mapped_column(Integer)  # FCFA

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus))
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    order: Mapped["Order"] = relationship(back_populates="history")


# --------------------------------------------------------------------------- #
# Paiements
# --------------------------------------------------------------------------- #
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    provider: Mapped[str] = mapped_column(String(60))  # ex. "mtn_momo"
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    reference: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)  # FCFA
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING
    )
    # Journal d'évènements du fournisseur (sans PIN ni secret — RM/NFR 11.2, §6.7).
    events: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    order: Mapped["Order"] = relationship(back_populates="payments")


class WebhookEvent(Base):
    """Évènements de webhook reçus, pour garantir l'idempotence (RM-07)."""

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# --------------------------------------------------------------------------- #
# Abonnements SaaS
# --------------------------------------------------------------------------- #
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), unique=True, index=True)
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan), default=SubscriptionPlan.TRIAL
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.TRIALING
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    product_limit: Mapped[int] = mapped_column(Integer, default=20)
    monthly_order_limit: Mapped[int] = mapped_column(Integer, default=50)
    # Facturation de l'abonnement SaaS (celui encaissé par la plateforme).
    amount: Mapped[int] = mapped_column(Integer, default=0)  # FCFA / mois
    grace_days: Mapped[int] = mapped_column(Integer, default=3)  # délai avant suspension
    auto_suspend: Mapped[bool] = mapped_column(Boolean, default=True)
    last_payment_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Rappelle si la boutique a été suspendue pour impayé (pour réactivation auto).
    suspended_for_nonpayment: Mapped[bool] = mapped_column(Boolean, default=False)

    shop: Mapped["Shop"] = relationship(back_populates="subscription")
    payments: Mapped[list["SubscriptionPayment"]] = relationship(back_populates="subscription")


class SubscriptionPayment(Base):
    """Historique des encaissements d'abonnement (versés à la plateforme)."""

    __tablename__ = "subscription_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # FCFA
    method: Mapped[str] = mapped_column(String(40), default="manual")
    reference: Mapped[str] = mapped_column(String(80))
    period_start: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    recorded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    subscription: Mapped["Subscription"] = relationship(back_populates="payments")


# --------------------------------------------------------------------------- #
# Notifications & audit
# --------------------------------------------------------------------------- #
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"), nullable=True, index=True)
    recipient: Mapped[str] = mapped_column(String(160))
    channel: Mapped[str] = mapped_column(String(30))  # whatsapp | email | sms | push
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(120))
    target: Mapped[str | None] = mapped_column(String(160), nullable=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"), nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
