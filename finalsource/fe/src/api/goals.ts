import { httpClient } from './httpClient';
import type { ApiSuccess } from './types';

export interface SavingGoal { goalId: number; goalType: 'Saving'; targetAmount: number; targetAchieved: number; startDate: string; endDate: string }
export interface ExpenseGoal { goalId: number; category: string; targetAmount: number }
export interface GoalsPayload { savingGoal: SavingGoal | null; expenseGoals: ExpenseGoal[] }
export type CreateGoalType = 'Saving' | 'Expense';
export interface CreateGoalInput { goal_type: CreateGoalType; category_id: number | null; target_amount: string; start_date: string; end_date: string }
export interface CreatedGoal { goalId: number }
export interface UpdateGoalInput { target_amount: number }
export interface UpdatedGoal { goalId: number; targetAmount: number }
const safeError = 'Unable to load goals.';

export async function getGoals(signal?: AbortSignal): Promise<GoalsPayload> {
  const response = await httpClient.get<ApiSuccess<unknown>>('/v1/goals', { signal });
  const envelope = exactRecord(response.data, ['success', 'message', 'data']);
  if (envelope.success !== true || typeof envelope.message !== 'string') throw new Error(safeError);
  const payload = exactRecord(envelope.data, ['savingGoal', 'expenseGoals']);
  if (!Array.isArray(payload.expenseGoals)) throw new Error(safeError);
  return { savingGoal: payload.savingGoal === null ? null : parseSaving(payload.savingGoal), expenseGoals: payload.expenseGoals.map(parseExpense) };
}

export async function createGoal(input: CreateGoalInput): Promise<CreatedGoal> {
  const response = await httpClient.post<ApiSuccess<unknown>>('/v1/goals', input);
  const envelope = exactRecord(response.data, ['success', 'message', 'data']);
  if (envelope.success !== true || envelope.message !== 'Goal created successfully') throw new Error('Could not create target at this time. Please try again later.');
  const payload = exactRecord(envelope.data, ['goal_id']);
  if (!positiveId(payload.goal_id)) throw new Error('Could not create target at this time. Please try again later.');
  return { goalId: payload.goal_id };
}

export async function updateGoal(goalId: number, input: UpdateGoalInput): Promise<UpdatedGoal> {
  if (!positiveId(goalId)) throw new Error('Cannot save changes at this time. Please try again later.');
  const response = await httpClient.put<ApiSuccess<unknown>>(`/v1/goals/${goalId}`, input);
  const envelope = exactRecord(response.data, ['success', 'message', 'data']);
  if (envelope.success !== true || envelope.message !== 'Goal updated successfully') throw new Error('Cannot save changes at this time. Please try again later.');
  const data = exactRecord(envelope.data, ['updated_goal']);
  const updated = exactRecord(data.updated_goal, ['goal_id', 'target_amount']);
  if (!positiveId(updated.goal_id) || updated.goal_id !== goalId || !money(updated.target_amount, false)) throw new Error('Cannot save changes at this time. Please try again later.');
  return { goalId: updated.goal_id, targetAmount: updated.target_amount };
}

function parseSaving(value: unknown): SavingGoal {
  const row = exactRecord(value, ['goal_id','goal_type','target_amount','target_achieved','start_date','end_date']);
  if (!positiveId(row.goal_id) || row.goal_type !== 'Saving' || !money(row.target_amount, false) || !money(row.target_achieved, true) || !date(row.start_date) || !date(row.end_date)) throw new Error(safeError);
  return { goalId: row.goal_id, goalType: 'Saving', targetAmount: row.target_amount, targetAchieved: row.target_achieved, startDate: row.start_date, endDate: row.end_date };
}
function parseExpense(value: unknown): ExpenseGoal {
  const row = exactRecord(value, ['goal_id','category','target_amount']);
  if (!positiveId(row.goal_id) || typeof row.category !== 'string' || row.category.trim().length === 0 || row.category.length > 160 || !money(row.target_amount, false)) throw new Error(safeError);
  return { goalId: row.goal_id, category: row.category, targetAmount: row.target_amount };
}
function exactRecord(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error(safeError);
  const row = value as Record<string, unknown>; const actual = Object.keys(row).sort(); const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) throw new Error(safeError); return row;
}
function positiveId(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value > 0; }
function money(value: unknown, signed: boolean): value is number { return typeof value === 'number' && Number.isFinite(value) && (signed || value > 0) && Math.abs(value) <= Number.MAX_SAFE_INTEGER && Number.isSafeInteger(value * 10_000); }
function date(value: unknown): value is string { if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false; const parsed = new Date(`${value}T00:00:00.000Z`); return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0,10) === value; }
