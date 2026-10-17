import { httpClient } from './httpClient';
import type { ApiSuccess } from './types';

export interface BankAccount {
  id: number;
  bank_name: string;
  account_type: string;
  branch_name: string;
  account_number_last_4: string;
  balance: number;
}

export interface AccountListResult {
  user_id: number;
  accounts: BankAccount[];
}

export interface CreateAccountInput {
  bank_name: string;
  account_type: string;
  branch_name?: string;
  account_number_full: string;
  balance: number;
}

export interface CreateAccountResult {
  account: BankAccount & { user_id: number };
}

export interface UpdateAccountInput {
  bank_name: string;
  account_type: string;
  branch_name?: string;
  account_number_full?: string;
  balance: number;
}

export interface UpdatedAccount {
  account_id: number;
  user_id: number;
  bank_name: string;
  account_type: string;
  branch_name: string;
  account_number_last_4: string;
  balance: number;
  updated_at: string;
}

export interface UpdateAccountResult {
  account: UpdatedAccount;
}

export interface DeleteAccountResult {
  deleted_account_id: number;
}

export interface RecentAccountTransaction {
  date: string;
  amount: number;
  description: string;
  status: string;
  receipt_id: string | null;
  type: 'Revenue' | 'Expense';
}

export interface AccountDetail extends BankAccount {
  recent_transactions: RecentAccountTransaction[];
}

export async function listAccounts(signal: AbortSignal): Promise<AccountListResult> {
  const response = await httpClient.get<ApiSuccess<AccountListResult>>('/v1/accounts', { signal });
  return response.data.data;
}

export async function createAccount(input: CreateAccountInput): Promise<CreateAccountResult> {
  const response = await httpClient.post<ApiSuccess<CreateAccountResult>>('/v1/accounts', input);
  return response.data.data;
}

export async function updateAccount(accountId: number, input: UpdateAccountInput): Promise<UpdateAccountResult> {
  const response = await httpClient.put<ApiSuccess<UpdateAccountResult>>(`/v1/accounts/${encodeURIComponent(String(accountId))}`, input);
  return response.data.data;
}

export async function deleteAccount(accountId: number): Promise<DeleteAccountResult> {
  const response = await httpClient.delete<ApiSuccess<DeleteAccountResult>>(`/v1/accounts/${encodeURIComponent(String(accountId))}`);
  return response.data.data;
}

export async function getAccountDetails(accountId: number, signal: AbortSignal): Promise<AccountDetail> {
  const response = await httpClient.get<ApiSuccess<unknown>>(`/v1/accounts/${encodeURIComponent(String(accountId))}`, { signal });
  return parseAccountDetail(response.data.data);
}

function parseAccountDetail(value: unknown): AccountDetail {
  const record = requireRecord(value);
  const id = requirePositiveInteger(record.id);
  const recentValue = record.recent_transactions;
  if (!Array.isArray(recentValue) || recentValue.length > 5) throw new Error('Invalid account detail response');

  return {
    id,
    bank_name: requireString(record.bank_name, 160),
    account_type: requireString(record.account_type, 64),
    branch_name: requireString(record.branch_name, 160, true),
    account_number_last_4: requireLastFour(record.account_number_last_4),
    balance: requireFiniteNumber(record.balance, true),
    recent_transactions: recentValue.map(parseRecentTransaction),
  };
}

function parseRecentTransaction(value: unknown): RecentAccountTransaction {
  const record = requireRecord(value);
  const type = record.type;
  const receipt = record.receipt_id;
  if (type !== 'Revenue' && type !== 'Expense') throw new Error('Invalid account detail response');
  if (receipt !== null && (typeof receipt !== 'string' || receipt.length > 255)) throw new Error('Invalid account detail response');
  const date = requireString(record.date, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('Invalid account detail response');

  return {
    date,
    amount: requireFiniteNumber(record.amount, false),
    description: requireString(record.description, 255, true),
    status: requireString(record.status, 32),
    receipt_id: receipt,
    type,
  };
}

function requireRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('Invalid account detail response');
  return value as Record<string, unknown>;
}

function requireString(value: unknown, maxLength: number, allowEmpty = false): string {
  if (typeof value !== 'string' || value.length > maxLength || (!allowEmpty && value.length === 0)) throw new Error('Invalid account detail response');
  return value;
}

function requirePositiveInteger(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) throw new Error('Invalid account detail response');
  return value;
}

function requireFiniteNumber(value: unknown, nonnegative: boolean): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || (nonnegative && value < 0)) throw new Error('Invalid account detail response');
  return value;
}

function requireLastFour(value: unknown): string {
  if (typeof value !== 'string' || !/^\d{4}$/.test(value)) throw new Error('Invalid account detail response');
  return value;
}
