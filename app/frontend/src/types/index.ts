export interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  role: 'merchant' | 'employee' | 'superadmin';
  is_active: boolean;
}

export interface Shop {
  id: number;
  owner_id: number;
  name: string;
  slug: string;
  logo_url?: string;
  banner_url?: string;
  description?: string;
  phone_whatsapp: string;
  email?: string;
  city?: string;
  neighborhood?: string;
  status: 'active' | 'suspended' | 'archived';
  suspended_reason?: string;
  min_order_amount: number;
  currency: string;
  theme_color?: string;
  created_at: string;
}

export interface Category {
  id: number;
  shop_id: number;
  name: string;
  order: number;
}

export interface Product {
  id: number;
  shop_id: number;
  category_id: number;
  name: string;
  description?: string;
  price: number;
  image_url?: string;
  sku?: string;
  stock: number;
  stock_alert_threshold: number;
  status: 'available' | 'discontinued' | 'hidden';
}

export interface ProductVariant {
  id: number;
  product_id: number;
  name: string;
  sku?: string;
  price: number;
  stock: number;
}

export interface CartItem {
  product_id: number;
  variant_id?: number;
  quantity: number;
  price: number;
}

export interface Customer {
  id: number;
  shop_id: number;
  phone: string;
  name: string;
  email?: string;
  is_blocked: boolean;
  block_reason?: string;
}

export interface Order {
  id: number;
  shop_id: number;
  customer_id?: number;
  reference: string;
  items: OrderItem[];
  subtotal: number;
  delivery_fee: number;
  discount: number;
  total: number;
  status: 'new' | 'confirmed' | 'preparing' | 'ready' | 'delivering' | 'delivered' | 'cancelled' | 'refunded';
  payment_status: 'pending' | 'paid' | 'failed';
  payment_method?: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string;
  delivery_address: string;
  delivery_zone?: string;
  created_at: string;
  updated_at: string;
}

export interface OrderItem {
  id: number;
  order_id: number;
  product_id: number;
  variant_id?: number;
  name: string;
  quantity: number;
  unit_price: number;
}

export interface Stats {
  revenue_today: number;
  revenue_week: number;
  revenue_month: number;
  orders_pending: number;
  orders_total: number;
  customers_total: number;
  avg_order_value: number;
}

export interface Subscription {
  id: number;
  shop_id: number;
  plan: 'trial' | 'starter' | 'business' | 'premium';
  status: 'active' | 'past_due' | 'cancelled';
  amount: number;
  current_period_end?: string;
  is_suspended: boolean;
}

export interface PaymentMethod {
  id: string;
  name: string;
  provider: string;
  enabled: boolean;
}
