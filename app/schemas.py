"""Schémas Pydantic pour l'API REST (validation serveur — NFR 11.2, §13).

Les prix ne sont jamais acceptés depuis le client pour un panier : seuls des
identifiants et des quantités le sont (RM-02).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from . import models


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    accept_terms: bool = True


class LoginIn(BaseModel):
    identifier: str = Field(description="E-mail ou téléphone")
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str


# --------------------------------------------------------------------------- #
# Boutique
# --------------------------------------------------------------------------- #
class ShopCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    sector: str | None = None
    whatsapp_number: str | None = None
    city: str | None = None


class ShopUpdateIn(BaseModel):
    name: str | None = None
    sector: str | None = None
    description: str | None = None
    theme_color: str | None = None
    whatsapp_number: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    city: str | None = None
    opening_hours: str | None = None
    is_open: bool | None = None
    closed_message: str | None = None
    min_order_amount: int | None = Field(default=None, ge=0)
    accept_cash_on_delivery: bool | None = None
    accept_mtn_momo: bool | None = None
    accept_orange_money: bool | None = None
    reserve_stock_on_confirm: bool | None = None


class ShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    sector: str | None
    theme_color: str
    city: str | None
    status: models.ShopStatus
    is_open: bool


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    position: int = 0


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    position: int
    is_active: bool


class VariantIn(BaseModel):
    name: str = Field(max_length=120)
    sku: str | None = None
    price: int | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    category_id: int | None = None
    image_url: str | None = None
    price: int = Field(ge=0)
    promo_price: int | None = Field(default=None, ge=0)
    sku: str | None = None
    stock: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    status: models.ProductStatus = models.ProductStatus.AVAILABLE
    variants: list[VariantIn] = Field(default_factory=list)


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sku: str | None
    price: int | None
    stock: int
    is_active: bool


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    category_id: int | None
    image_url: str | None
    price: int
    promo_price: int | None
    sku: str | None
    stock: int
    low_stock_threshold: int
    status: models.ProductStatus
    variants: list[VariantOut] = []


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_url: str
    alt_text: str | None
    position: int
    is_primary: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Commandes
# --------------------------------------------------------------------------- #
class CartItemIn(BaseModel):
    product_id: int
    variant_id: int | None = None
    quantity: int = Field(ge=1)


class CheckoutIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: str = Field(min_length=6, max_length=40)
    payment_method: models.PaymentMethod
    delivery_zone_id: int | None = None
    is_pickup: bool = False
    delivery_city: str | None = None
    delivery_district: str | None = None
    delivery_details: str | None = None
    customer_note: str | None = None
    marketing_consent: bool = False


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_name: str
    variant_name: str | None
    unit_price: int
    quantity: int
    line_total: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    customer_name: str
    customer_phone: str
    subtotal: int
    delivery_fee: int
    discount: int
    total: int
    payment_method: models.PaymentMethod
    status: models.OrderStatus
    created_at: datetime
    items: list[OrderItemOut] = []


class CheckoutOut(BaseModel):
    order: OrderOut
    whatsapp_link: str
    payment_instructions: str | None = None


class StatusChangeIn(BaseModel):
    status: models.OrderStatus
    note: str | None = None


# --------------------------------------------------------------------------- #
# Paiements
# --------------------------------------------------------------------------- #
class PaymentWebhookIn(BaseModel):
    event_id: str
    payment_reference: str
    status: models.PaymentStatus
    provider_reference: str | None = None
