import { httpClient } from './httpClient';
import type { ApiSuccess } from './types';

const monthOrder = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;
export type ExpenseMonth = (typeof monthOrder)[number];

export interface MonthlyExpense {
  month: ExpenseMonth;
  totalExpense: number;
}

export interface ExpenseSummaryPayload {
  data: MonthlyExpense[];
}

export interface ExpenseBreakdownItem {
  item_description: string;
  amount: number;
  date: string;
}

export interface ExpenseBreakdownCategory {
  category: string;
  Total: number;
  changePercent: number;
  subCategories: ExpenseBreakdownItem[];
}

export interface ExpenseBreakdownPayload {
  data: ExpenseBreakdownCategory[];
}

export async function getExpenseSummary(signal: AbortSignal): Promise<ExpenseSummaryPayload> {
  const response = await httpClient.get<ApiSuccess<unknown>>('/v1/expenses/summary', { signal });
  return parseExpenseSummary(response.data.data);
}

export async function getExpenseBreakdown(month: string, signal: AbortSignal): Promise<ExpenseBreakdownPayload> {
  if (!isValidMonth(month)) throw new Error('Invalid expense breakdown month');
  const response = await httpClient.get<ApiSuccess<unknown>>('/v1/expenses/breakdown', { params: { month }, signal });
  return parseExpenseBreakdown(response.data.data);
}

function parseExpenseSummary(value: unknown): ExpenseSummaryPayload {
  const record = requireExactRecord(value, ['data'], 'Invalid expense summary response');
  if (!Array.isArray(record.data)) throw new Error('Invalid expense summary response');
  const seen = new Set<ExpenseMonth>();
  let previousIndex = -1;
  const data = record.data.map((item) => {
    const row = requireExactRecord(item, ['month', 'totalExpense'], 'Invalid expense summary response');
    if (typeof row.month !== 'string' || !monthOrder.includes(row.month as ExpenseMonth)) throw new Error('Invalid expense summary response');
    const month = row.month as ExpenseMonth;
    const index = monthOrder.indexOf(month);
    if (seen.has(month) || index <= previousIndex) throw new Error('Invalid expense summary response');
    if (typeof row.totalExpense !== 'number' || !Number.isFinite(row.totalExpense) || row.totalExpense < 0) throw new Error('Invalid expense summary response');
    seen.add(month);
    previousIndex = index;
    return { month, totalExpense: row.totalExpense };
  });
  return { data };
}

function parseExpenseBreakdown(value: unknown): ExpenseBreakdownPayload {
  const message = 'Invalid expense breakdown response';
  const record = requireExactRecord(value, ['data'], message);
  if (!Array.isArray(record.data)) throw new Error(message);
  const categories = new Set<string>();
  const data = record.data.map((item) => {
    const row = requireExactRecord(item, ['category', 'Total', 'changePercent', 'subCategories'], message);
    if (typeof row.category !== 'string' || row.category.trim().length === 0 || row.category.length > 160 || categories.has(row.category)) throw new Error(message);
    if (typeof row.Total !== 'number' || !Number.isFinite(row.Total) || row.Total < 0 || row.Total > Number.MAX_SAFE_INTEGER) throw new Error(message);
    if (typeof row.changePercent !== 'number' || !Number.isFinite(row.changePercent) || Math.abs(row.changePercent) > Number.MAX_SAFE_INTEGER) throw new Error(message);
    if (!Array.isArray(row.subCategories) || row.subCategories.length === 0) throw new Error(message);
    categories.add(row.category);
    const subCategories = row.subCategories.map((subItem) => {
      const subRow = requireExactRecord(subItem, ['item_description', 'amount', 'date'], message);
      if (typeof subRow.item_description !== 'string' || subRow.item_description.trim().length === 0 || subRow.item_description.length > 255) throw new Error(message);
      if (typeof subRow.amount !== 'number' || !Number.isFinite(subRow.amount) || subRow.amount < 0 || subRow.amount > Number.MAX_SAFE_INTEGER) throw new Error(message);
      if (typeof subRow.date !== 'string' || !isValidDate(subRow.date)) throw new Error(message);
      return { item_description: subRow.item_description, amount: subRow.amount, date: subRow.date };
    });
    return { category: row.category, Total: row.Total, changePercent: row.changePercent, subCategories };
  });
  return { data };
}

function requireExactRecord(value: unknown, keys: readonly string[], message: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error(message);
  const record = value as Record<string, unknown>;
  const actualKeys = Object.keys(record).sort();
  const expectedKeys = [...keys].sort();
  if (actualKeys.length !== expectedKeys.length || actualKeys.some((key, index) => key !== expectedKeys[index])) throw new Error(message);
  return record;
}

function isValidMonth(value: string): boolean {
  return /^[1-9]\d{3}-(0[1-9]|1[0-2])$/.test(value);
}

function isValidDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
