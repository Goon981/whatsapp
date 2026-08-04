import { apiClient } from './client';
import { Shop } from '../types';

export interface CreateShopPayload {
  name: string;
  phone_whatsapp: string;
  city?: string;
  neighborhood?: string;
  min_order_amount?: number;
  theme_color?: string;
}

export interface UpdateShopPayload extends Partial<CreateShopPayload> {
  logo_url?: string;
  banner_url?: string;
  description?: string;
}

export const shopsAPI = {
  list: async (): Promise<Shop[]> => {
    const { data } = await apiClient.get<Shop[]>('/shops');
    return data;
  },

  get: async (shopId: number): Promise<Shop> => {
    const { data } = await apiClient.get<Shop>(`/shops/${shopId}`);
    return data;
  },

  create: async (payload: CreateShopPayload): Promise<Shop> => {
    const { data } = await apiClient.post<Shop>('/shops', payload);
    return data;
  },

  update: async (shopId: number, payload: UpdateShopPayload): Promise<Shop> => {
    const { data } = await apiClient.patch<Shop>(`/shops/${shopId}`, payload);
    return data;
  },

  getPublic: async (slug: string): Promise<Shop> => {
    const { data } = await apiClient.get<Shop>(`/storefront/${slug}`);
    return data;
  },
};
