import axios from 'axios';
import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { updateGoal } from '../../api/goals';

const invalidAmountMessage = 'Target amount must be greater than 0.';
const fallbackError = 'Cannot save changes at this time. Please try again later.';

interface AdjustGoalModalProps {
  readonly goalId: number;
  readonly currentTargetAmount: number;
  readonly onClose: () => void;
  readonly onSuccess: () => void;
}

export function AdjustGoalModal({ goalId, currentTargetAmount, onClose, onSuccess }: AdjustGoalModalProps) {
  const titleId = useId();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
  const [targetAmount, setTargetAmount] = useState(String(currentTargetAmount));
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    mounted.current = true;
    inputRef.current?.focus();
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === 'Escape' && !isLoading) onClose();
    }
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [isLoading, onClose]);

  async function handleSave(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isLoading) return;
    const amount = Number(targetAmount);
    if (!validMoneyInput(targetAmount, amount)) {
      setFieldError(invalidAmountMessage);
      setError(null);
      return;
    }

    setFieldError(null);
    setError(null);
    setIsLoading(true);
    try {
      await updateGoal(goalId, { target_amount: amount });
      if (!mounted.current) return;
      onClose();
      onSuccess();
    } catch (failure: unknown) {
      if (!mounted.current) return;
      const status = axios.isAxiosError(failure) ? failure.response?.status : undefined;
      if (status === 400) setFieldError(invalidAmountMessage);
      else if (status === 403) setError('You do not have permission to edit this target');
      else if (status === 404) setError('This target is no longer available.');
      else setError(fallbackError);
    } finally {
      if (mounted.current) setIsLoading(false);
    }
  }

  return <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-[#262626]/35 p-4" role="presentation">
    <section role="dialog" aria-modal="true" aria-labelledby={titleId} className="relative my-6 w-full max-w-[520px] rounded-[18px] bg-white px-8 pb-9 pt-8 shadow-[0_24px_60px_rgba(31,41,55,0.20)] sm:px-16">
      <button type="button" onClick={onClose} disabled={isLoading} aria-label="Close adjust goal dialog" className="absolute right-7 top-6 text-[34px] leading-none text-[#555] focus:outline-none focus:ring-2 focus:ring-[#299d91] disabled:opacity-50">×</button>
      <h2 id={titleId} className="pr-10 text-[22px] font-semibold text-[#4f4f55]">Adjusting Goals</h2>
      <form onSubmit={(event) => { void handleSave(event); }} className="mt-7 space-y-5" noValidate>
        <label htmlFor={inputId} className="block">
          <span className="mb-2 block text-[16px] font-semibold text-[#55555c]">Target Amount</span>
          <div className="relative">
            <span className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[#8b8b8f]">$</span>
            <input ref={inputRef} id={inputId} value={targetAmount} onChange={(event) => setTargetAmount(event.target.value)} inputMode="decimal" autoComplete="off" disabled={isLoading} aria-invalid={Boolean(fieldError)} aria-describedby={fieldError ? `${inputId}-error` : undefined} className={`${inputClass} pl-9`}/>
          </div>
          {fieldError && <span id={`${inputId}-error`} role="alert" className="mt-1.5 block text-sm text-red-700">{fieldError}</span>}
        </label>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-center">
          <button type="button" onClick={onClose} disabled={isLoading} className="h-12 min-w-[150px] rounded border border-[#299d91] px-7 font-semibold text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91] disabled:opacity-50">Cancel</button>
          <button type="submit" disabled={isLoading} className="flex h-12 min-w-[190px] items-center justify-center rounded bg-[#299d91] px-8 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#147b71] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70">{isLoading ? <><span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-r-transparent" aria-hidden="true"/>Saving…</> : 'Save'}</button>
        </div>
      </form>
    </section>
  </div>;
}

const inputClass = 'h-[56px] w-full rounded-[9px] border border-[#d4d4d7] bg-white px-5 text-[#55555c] outline-none placeholder:text-[#a0a0a4] focus:border-[#299d91] focus:ring-2 focus:ring-[#299d91]/25 disabled:bg-[#f4f4f5]';

function validMoneyInput(raw: string, amount: number): boolean {
  return /^(?:0|[1-9]\d{0,11})(?:\.\d{1,4})?$/.test(raw) && Number.isFinite(amount) && amount > 0 && Number.isSafeInteger(amount * 10_000);
}
