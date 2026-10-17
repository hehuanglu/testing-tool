import { httpClient } from './httpClient';
import type { ApiSuccess } from './types';

export interface MonthlySavings {
  month: string;
  amount: number;
}

export interface SavingsSummaryPayload {
  userId: number;
  year: number;
  thisYear: MonthlySavings[];
  lastYear: MonthlySavings[];
}

const safeError = 'Unable to load data. Please try again later.';

export async function fetchSavingsSummary(year: number, signal?: AbortSignal): Promise<SavingsSummaryPayload> {
  if (!Number.isInteger(year) || year < 1000 || year > 9999) throw new Error(safeError);
  const response = await httpClient.get<ApiSuccess<unknown>>('/v1/savings/summary', { params: { year }, signal });
  const envelope = exactRecord(response.data, ['success', 'message', 'data']);
  if (envelope.success !== true || envelope.message !== 'Savings summary retrieved successfully.') throw new Error(safeError);
  const payload = exactRecord(envelope.data, ['user_id', 'year', 'summary']);
  const summary = exactRecord(payload.summary, ['this_year', 'last_year']);
  if (!positiveId(payload.user_id) || payload.year !== year || !Array.isArray(summary.this_year) || !Array.isArray(summary.last_year)) {
    throw new Error(safeError);
  }
  return {
    userId: payload.user_id,
    year: payload.year,
    thisYear: parseSeries(summary.this_year),
    lastYear: parseSeries(summary.last_year),
  };
}

function parseSeries(value: unknown[]): MonthlySavings[] {
  const seen = new Set<string>();
  return value.map((item) => {
    const row = exactRecord(item, ['month', 'amount']);
    if (typeof row.month !== 'string' || !/^(0[1-9]|1[0-2])$/.test(row.month) || seen.has(row.month) || !money(row.amount)) {
      throw new Error(safeError);
    }
    seen.add(row.month);
    return { month: row.month, amount: row.amount };
  });
}

function exactRecord(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error(safeError);
  const row = value as Record<string, unknown>;
  const actual = Object.keys(row).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) throw new Error(safeError);
  return row;
}

function positiveId(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

function money(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= Number.MAX_SAFE_INTEGER && Number.isSafeInteger(value * 10_000);
}
