import axios from 'axios';
import { useEffect, useId, useState, type FormEvent, type ReactNode } from 'react';
import { createGoal, type CreateGoalType } from '../../api/goals';
import { listCategoryOptions, type CategoryOption } from '../../api/transactions';

const fallbackError = 'Could not create target at this time. Please try again later.';
type FieldName = 'goalType' | 'categoryId' | 'targetAmount' | 'startDate' | 'endDate' | 'form';
type FieldErrors = Partial<Record<FieldName, string>>;

interface CreateGoalModalProps {
  readonly onCancel: () => void;
  readonly onCreated: () => void;
}

export function CreateGoalModal({ onCancel, onCreated }: CreateGoalModalProps) {
  const titleId = useId();
  const [goalType, setGoalType] = useState<CreateGoalType>('Saving');
  const [categoryId, setCategoryId] = useState('');
  const [targetAmount, setTargetAmount] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [categoryLoadError, setCategoryLoadError] = useState<string | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (goalType !== 'Expense') return;
    const controller = new AbortController();
    setCategoryLoadError(null);
    void listCategoryOptions(controller.signal)
      .then(setCategories)
      .catch((failure: unknown) => {
        if (!axios.isCancel(failure)) setCategoryLoadError('Could not load expense categories.');
      });
    return () => controller.abort();
  }, [goalType]);

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!/^(?:0|[1-9]\d{0,14})(?:\.\d{1,4})?$/.test(targetAmount) || Number(targetAmount) <= 0) next.targetAmount = 'Target amount must be greater than 0.';
    if (!startDate) next.startDate = 'Please select a start date.';
    if (!endDate) next.endDate = 'Please select an end date.';
    else if (startDate && endDate <= startDate) next.endDate = 'End date must be after start date.';
    if (goalType === 'Expense' && !categoryId) next.categoryId = 'Please select an expense category.';
    return next;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isLoading) return;
    const nextErrors = validate();
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    setErrors({});
    setIsLoading(true);
    try {
      await createGoal({
        goal_type: goalType,
        category_id: goalType === 'Expense' ? Number(categoryId) : null,
        target_amount: targetAmount,
        start_date: startDate,
        end_date: endDate,
      });
      onCreated();
    } catch (failure: unknown) {
      const message = safeApiMessage(failure);
      if (message === 'Please select an expense category.' || message === 'Please select a valid expense category.') setErrors({ categoryId: message });
      else if (message === 'End date must be after start date.') setErrors({ endDate: message });
      else setErrors({ form: message });
    } finally {
      setIsLoading(false);
    }
  }

  return <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-[#262626]/35 p-4" role="presentation">
    <section role="dialog" aria-modal="true" aria-labelledby={titleId} className="relative my-6 w-full max-w-[520px] rounded-[18px] bg-white px-8 pb-9 pt-8 shadow-[0_24px_60px_rgba(31,41,55,0.20)] sm:px-16" data-node-id="416:6052">
      <button type="button" onClick={onCancel} disabled={isLoading} aria-label="Close create goal dialog" className="absolute right-7 top-6 text-[34px] leading-none text-[#555] focus:outline-none focus:ring-2 focus:ring-[#299d91] disabled:opacity-50">×</button>
      <h2 id={titleId} className="pr-10 text-[22px] font-semibold text-[#4f4f55]">Add a new goal</h2>
      <form onSubmit={(event)=>{ void handleSubmit(event); }} className="mt-7 space-y-5" noValidate>
        <fieldset>
          <legend className="mb-2 text-[16px] font-semibold text-[#55555c]">Goal Type</legend>
          <div className="grid grid-cols-2 gap-3">
            <GoalTypeChoice label="Overall Savings" value="Saving" selected={goalType} disabled={isLoading} onChange={setGoalType}/>
            <GoalTypeChoice label="Expense Limit" value="Expense" selected={goalType} disabled={isLoading} onChange={setGoalType}/>
          </div>
        </fieldset>

        {goalType === 'Expense' && <Field label="Category" error={errors.categoryId ?? categoryLoadError}>
          <select value={categoryId} onChange={(event)=>setCategoryId(event.target.value)} disabled={isLoading || categoryLoadError !== null} aria-invalid={Boolean(errors.categoryId)} className={inputClass}>
            <option value="">Select an expense category</option>
            {categories.map((category)=><option key={category.category_id} value={category.category_id}>{category.name}</option>)}
          </select>
        </Field>}

        <Field label="Target Amount" error={errors.targetAmount}>
          <div className="relative"><span className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[#8b8b8f]">$</span><input value={targetAmount} onChange={(event)=>setTargetAmount(event.target.value)} inputMode="decimal" autoComplete="off" placeholder="500000" disabled={isLoading} aria-invalid={Boolean(errors.targetAmount)} className={`${inputClass} pl-9`}/></div>
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Start Date" error={errors.startDate}><input type="date" value={startDate} onChange={(event)=>setStartDate(event.target.value)} disabled={isLoading} aria-invalid={Boolean(errors.startDate)} className={inputClass}/></Field>
          <Field label="End Date" error={errors.endDate}><input type="date" value={endDate} onChange={(event)=>setEndDate(event.target.value)} disabled={isLoading} aria-invalid={Boolean(errors.endDate)} className={inputClass}/></Field>
        </div>

        {errors.form && <p role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{errors.form}</p>}
        <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-center">
          <button type="button" onClick={onCancel} disabled={isLoading} className="h-12 min-w-[150px] rounded border border-[#299d91] px-7 font-semibold text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91] disabled:opacity-50">Cancel</button>
          <button type="submit" disabled={isLoading} className="flex h-12 min-w-[190px] items-center justify-center rounded bg-[#299d91] px-8 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#147b71] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70">{isLoading?<><span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-r-transparent" aria-hidden="true"/>Saving…</>:'Save'}</button>
        </div>
      </form>
    </section>
  </div>;
}

const inputClass = 'h-[56px] w-full rounded-[9px] border border-[#d4d4d7] bg-white px-5 text-[#55555c] outline-none placeholder:text-[#a0a0a4] focus:border-[#299d91] focus:ring-2 focus:ring-[#299d91]/25 disabled:bg-[#f4f4f5]';

function Field({ label, error, children }: { readonly label: string; readonly error?: string | null; readonly children: ReactNode }) {
  return <label className="block"><span className="mb-2 block text-[16px] font-semibold text-[#55555c]">{label}</span>{children}{error&&<span className="mt-1.5 block text-sm text-red-700">{error}</span>}</label>;
}

function GoalTypeChoice({ label, value, selected, disabled, onChange }: { readonly label:string; readonly value:CreateGoalType; readonly selected:CreateGoalType; readonly disabled:boolean; readonly onChange:(value:CreateGoalType)=>void }) {
  return <label className={`flex min-h-12 items-center rounded-[9px] border px-4 text-sm font-medium ${selected===value?'border-[#299d91] bg-[#eaf7f5] text-[#177d74]':'border-[#d4d4d7] text-[#68686d]'}`}><input type="radio" name="goalType" value={value} checked={selected===value} onChange={()=>onChange(value)} disabled={disabled} className="mr-2 accent-[#299d91]"/>{label}</label>;
}

function safeApiMessage(failure: unknown): string {
  if (!axios.isAxiosError(failure)) return fallbackError;
  const data: unknown = failure.response?.data;
  if (typeof data !== 'object' || data === null || Array.isArray(data) || !('message' in data)) return fallbackError;
  const message = data.message;
  return typeof message === 'string' && message.length <= 160 ? message : fallbackError;
}
