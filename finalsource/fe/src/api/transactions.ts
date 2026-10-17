import { httpClient } from './httpClient';
import type { ApiSuccess } from './types';

export type TransactionType = 'Revenue' | 'Expense';
export type TransactionFilter = 'All' | TransactionType;

export interface Transaction {
  transactionId: number;
  accountId: number;
  transactionDate: string;
  type: TransactionType;
  itemDescription: string;
  shopName: string;
  amount: number;
  paymentMethod: string;
  status: string;
  receiptId: string | null;
  createdAt: string;
  category_id?: number;
}

export interface AccountOption {
  accountId: number;
}

export interface CategoryOption {
  category_id: number;
  name: string;
}

export interface CreateTransactionInput {
  accountId: number;
  transactionDate: string;
  type: TransactionType;
  itemDescription: string;
  category_id: number;
  shopName: string;
  amount: string;
  paymentMethod: string;
  status: string;
}

export type CreatedTransaction = Omit<Transaction, 'category_id'> & { category_id: number };

export interface TransactionListResult {
  data: Transaction[];
  total: number;
  hasMore: boolean;
}

interface ListTransactionsParams {
  type: TransactionFilter;
  limit: number;
  offset: number;
  signal?: AbortSignal;
}

export async function listTransactions({ type, limit, offset, signal }: ListTransactionsParams): Promise<TransactionListResult> {
  const response = await httpClient.get<ApiSuccess<TransactionListResult>>('/v1/transactions', {
    params: { type, limit, offset },
    signal,
  });
  return response.data.data;
}

export async function listAccountOptions(signal?: AbortSignal): Promise<AccountOption[]> {
  const response = await httpClient.get<ApiSuccess<AccountOption[]>>('/v1/accounts/options', { signal });
  return response.data.data;
}

export async function listCategoryOptions(signal?: AbortSignal): Promise<CategoryOption[]> {
  const response = await httpClient.get<ApiSuccess<CategoryOption[]>>('/v1/categories/options', { signal });
  return response.data.data;
}

export async function createTransaction(input: CreateTransactionInput): Promise<CreatedTransaction> {
  const response = await httpClient.post<ApiSuccess<CreatedTransaction>>('/v1/transactions', input);
  return response.data.data;
}
