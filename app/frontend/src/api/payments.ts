import { apiClient } from './client';

export interface InitializePaymentPayload {
  order_id: number;
  payment_method: 'cash' | 'mtn_momo' | 'orange_money';
  amount: number;
}

export interface PaymentResponse {
  payment_id: string;
  status: string;
  redirect_url?: string;
}

export const paymentsAPI = {
  initialize: async (payload: InitializePaymentPayload): Promise<PaymentResponse> => {
    const { data } = await apiClient.post<PaymentResponse>('/payments/initialize', payload);
    return data;
  },

  verify: async (paymentId: string): Promise<{ status: string; order_id?: number }> => {
    const { data } = await apiClient.get(`/payments/${paymentId}`);
    return data;
  },

  listMethods: async (): Promise<any[]> => {
    const { data } = await apiClient.get('/payments/methods');
    return data;
  },
};
