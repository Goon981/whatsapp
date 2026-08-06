import { apiClient } from './client';
import { Category, Product, ProductVariant } from '../types';

export interface CreateProductPayload {
  category_id: number;
  name: string;
  description?: string;
  price: number;
  image_url?: string;
  sku?: string;
  stock: number;
  stock_alert_threshold?: number;
}

export interface UpdateProductPayload extends Partial<CreateProductPayload> {
  status?: 'available' | 'discontinued' | 'hidden';
}

export const catalogAPI = {
  categories: {
    list: async (shopId: number): Promise<Category[]> => {
      const { data } = await apiClient.get<Category[]>(`/shops/${shopId}/catalog/categories`);
      return data;
    },

    create: async (shopId: number, name: string): Promise<Category> => {
      const { data } = await apiClient.post<Category>(`/shops/${shopId}/catalog/categories`, { name });
      return data;
    },
  },

  products: {
    list: async (shopId: number, params?: { category_id?: number }): Promise<Product[]> => {
      const { data } = await apiClient.get<Product[]>(`/shops/${shopId}/catalog/products`, { params });
      return data;
    },

    get: async (shopId: number, productId: number): Promise<Product> => {
      const { data } = await apiClient.get<Product>(`/shops/${shopId}/catalog/products/${productId}`);
      return data;
    },

    create: async (shopId: number, payload: CreateProductPayload): Promise<Product> => {
      const { data } = await apiClient.post<Product>(`/shops/${shopId}/catalog/products`, payload);
      return data;
    },

    update: async (shopId: number, productId: number, payload: UpdateProductPayload): Promise<Product> => {
      const { data } = await apiClient.patch<Product>(`/shops/${shopId}/catalog/products/${productId}`, payload);
      return data;
    },

    delete: async (shopId: number, productId: number): Promise<void> => {
      await apiClient.delete(`/shops/${shopId}/catalog/products/${productId}`);
    },

    uploadImage: async (shopId: number, productId: number, files: File | File[]): Promise<{ image_url: string } | { image_url: string }[]> => {
      const formData = new FormData();
      const fileList = Array.isArray(files) ? files : [files];
      fileList.forEach((file) => {
        formData.append('files', file);
      });
      const { data } = await apiClient.post(`/shops/${shopId}/products/${productId}/images`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return data;
    },
  },

  variants: {
    create: async (shopId: number, productId: number, variant: Partial<ProductVariant>): Promise<ProductVariant> => {
      const { data } = await apiClient.post<ProductVariant>(
        `/shops/${shopId}/catalog/products/${productId}/variants`,
        variant
      );
      return data;
    },

    update: async (shopId: number, productId: number, variantId: number, payload: Partial<ProductVariant>): Promise<ProductVariant> => {
      const { data } = await apiClient.patch<ProductVariant>(
        `/shops/${shopId}/catalog/products/${productId}/variants/${variantId}`,
        payload
      );
      return data;
    },
  },
};
