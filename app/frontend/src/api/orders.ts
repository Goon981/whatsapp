import { apiClient } from './client';
import { Order } from '../types';

export interface CheckoutPayload {
  shop_slug: string;
  items: Array<{ product_id: number; variant_id?: number; quantity: number }>;
  customer_name: string;
  customer_phone: string;
  customer_email?: string;
  delivery_address: string;
  delivery_zone?: string;
  payment_method: 'cash' | 'mtn_momo' | 'orange_money';
}

export const ordersAPI = {
  checkout: async (payload: CheckoutPayload): Promise<Order> => {
    const { data } = await apiClient.post<Order>('/checkout', payload);
    return data;
  },

  list: async (shopId: number, params?: { status?: string; limit?: number; offset?: number }): Promise<Order[]> => {
    const { data } = await apiClient.get<Order[]>(`/shops/${shopId}/orders`, { params });
    return data;
  },

  get: async (shopId: number, orderId: number): Promise<Order> => {
    const { data } = await apiClient.get<Order>(`/shops/${shopId}/orders/${orderId}`);
    return data;
  },

  updateStatus: async (shopId: number, orderId: number, status: string): Promise<Order> => {
    const { data } = await apiClient.patch<Order>(`/shops/${shopId}/orders/${orderId}`, { status });
    return data;
  },

  cancel: async (shopId: number, orderId: number): Promise<Order> => {
    const { data } = await apiClient.post<Order>(`/shops/${shopId}/orders/${orderId}/cancel`);
    return data;
  },

  getCustomerOrders: async (shopSlug: string): Promise<Order[]> => {
    const { data } = await apiClient.get<Order[]>(`/storefront/${shopSlug}/orders`);
    return data;
  },
};
