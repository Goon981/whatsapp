import { apiClient } from './client';
import { Stats } from '../types';

export const statsAPI = {
  getShopStats: async (shopId: number): Promise<Stats> => {
    const { data } = await apiClient.get<Stats>(`/shops/${shopId}/stats`);
    return data;
  },

  getPlatformOverview: async (): Promise<any> => {
    const { data } = await apiClient.get('/admin/overview');
    return data;
  },

  getBillingOverview: async (): Promise<any> => {
    const { data } = await apiClient.get('/admin/billing/overview');
    return data;
  },
};
