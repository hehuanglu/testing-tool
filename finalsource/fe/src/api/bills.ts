import { httpClient } from './httpClient';

export interface Bill {
  billId: number;
  userId: number;
  itemDescription: string;
  logoUrl: string;
  dueDate: string;
  lastChargeDate: string;
  Amount: number;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function calendarDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function parseBill(value: unknown): Bill {
  if (!record(value) || typeof value.billId !== 'number' || !Number.isSafeInteger(value.billId) || value.billId < 1 ||
      typeof value.userId !== 'number' || !Number.isSafeInteger(value.userId) || value.userId < 1 ||
      typeof value.itemDescription !== 'string' || value.itemDescription.length > 255 ||
      typeof value.logoUrl !== 'string' || value.logoUrl.length > 2048 ||
      !calendarDate(value.dueDate) || !calendarDate(value.lastChargeDate) ||
      typeof value.Amount !== 'number' || !Number.isFinite(value.Amount) || value.Amount <= 0) {
    throw new Error('Invalid bills response');
  }
  return {
    billId: value.billId, userId: value.userId, itemDescription: value.itemDescription,
    logoUrl: value.logoUrl, dueDate: value.dueDate, lastChargeDate: value.lastChargeDate, Amount: value.Amount,
  };
}

export async function fetchUpcomingBills(signal: AbortSignal): Promise<Bill[]> {
  const token = localStorage.getItem('finebank.accessToken') ?? sessionStorage.getItem('finebank.accessToken');
  const response = await httpClient.get<unknown>('/v1/bills', {
    signal, headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const envelope: unknown = response.data;
  if (!record(envelope) || envelope.success !== true || !record(envelope.data) || !Array.isArray(envelope.data.data)) {
    throw new Error('Invalid bills response');
  }
  return envelope.data.data.map(parseBill);
}
