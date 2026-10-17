import { useState, type FormEvent } from 'react';
import axios from 'axios';
import { Link, useNavigate } from 'react-router-dom';
import { createAccount } from '../api/accounts';
import type { ApiError } from '../api/types';

type FieldName = 'bank_name' | 'account_type' | 'branch_name' | 'account_number_full' | 'balance';
type FieldErrors = Partial<Record<FieldName, string>>;

const duplicateMessage = 'This account already exists in your list.';
const systemMessage = 'Unable to add account at this time. Please try again later.';

function fieldForMessage(message: string): FieldName | null {
  if (message.includes('bank_name')) return 'bank_name';
  if (message.includes('account_type')) return 'account_type';
  if (message.includes('branch_name')) return 'branch_name';
  if (message.includes('account_number_full')) return 'account_number_full';
  if (message.includes('balance')) return 'balance';
  return null;
}

export function AddAccountPage() {
  const navigate = useNavigate();
  const [bankName, setBankName] = useState('');
  const [accountType, setAccountType] = useState('');
  const [branchName, setBranchName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [balance, setBalance] = useState('0');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!bankName.trim()) errors.bank_name = 'Bank is required.';
    if (!accountType.trim()) errors.account_type = 'Account type is required.';
    if (!/^[0-9]{4,34}$/.test(accountNumber.trim())) errors.account_number_full = 'Account number must contain 4 to 34 digits.';
    const numericBalance = Number(balance);
    if (!balance.trim() || !Number.isFinite(numericBalance) || numericBalance < 0) errors.balance = 'Initial balance must be a number greater than or equal to 0.';
    return errors;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isLoading) return;
    setFormError('');
    setSuccessMessage('');
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsLoading(true);
    try {
      await createAccount({
        bank_name: bankName.trim(),
        account_type: accountType.trim(),
        branch_name: branchName.trim() || undefined,
        account_number_full: accountNumber.trim(),
        balance: Number(balance),
      });
      setAccountNumber('');
      setSuccessMessage('Account added successfully');
      window.setTimeout(() => navigate('/accounts', { replace: true }), 700);
    } catch (error: unknown) {
      if (!axios.isAxiosError<ApiError>(error)) {
        setFormError(systemMessage);
        return;
      }
      const status = error.response?.status;
      const message = error.response?.data?.message;
      if (status === 409) {
        setFormError(duplicateMessage);
      } else if (status === 400 && message) {
        const messages = Array.isArray(message) ? message : [message];
        const nextErrors: FieldErrors = {};
        for (const item of messages) {
          const field = fieldForMessage(item);
          if (field && !nextErrors[field]) nextErrors[field] = item;
        }
        setFieldErrors(nextErrors);
        if (Object.keys(nextErrors).length === 0) setFormError('Please correct the invalid account data.');
      } else {
        setFormError(systemMessage);
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f6f6] px-4 py-10 text-[#191919] sm:px-8">
      <div className="mx-auto max-w-3xl">
        <Link className="mb-6 inline-flex rounded text-sm font-semibold text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2" to="/accounts">
          ← Back to accounts
        </Link>
        <section className="rounded-xl bg-white p-6 shadow-[0_20px_40px_rgba(76,103,100,0.12)] sm:p-10" aria-labelledby="add-account-title">
          <div className="mb-8">
            <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-[#299d91]">Balances</p>
            <h1 id="add-account-title" className="text-3xl font-bold">Add a new account</h1>
            <p className="mt-2 text-sm text-[#666]">Link a bank account or wallet for financial tracking.</p>
          </div>

          <form className="grid gap-6 sm:grid-cols-2" onSubmit={handleSubmit} noValidate>
            <FormField id="bank_name" label="Bank / Wallet Name" error={fieldErrors.bank_name}>
              <input id="bank_name" name="bank_name" value={bankName} onChange={(event) => setBankName(event.target.value)} maxLength={160} autoComplete="organization" aria-invalid={Boolean(fieldErrors.bank_name)} aria-describedby={fieldErrors.bank_name ? 'bank_name-error' : undefined} className={inputClass} />
            </FormField>
            <FormField id="account_type" label="Account Type" error={fieldErrors.account_type}>
              <input id="account_type" name="account_type" value={accountType} onChange={(event) => setAccountType(event.target.value)} maxLength={64} autoComplete="off" aria-invalid={Boolean(fieldErrors.account_type)} aria-describedby={fieldErrors.account_type ? 'account_type-error' : undefined} className={inputClass} />
            </FormField>
            <FormField id="branch_name" label="Branch (optional)" error={fieldErrors.branch_name}>
              <input id="branch_name" name="branch_name" value={branchName} onChange={(event) => setBranchName(event.target.value)} maxLength={160} autoComplete="off" aria-invalid={Boolean(fieldErrors.branch_name)} aria-describedby={fieldErrors.branch_name ? 'branch_name-error' : undefined} className={inputClass} />
            </FormField>
            <FormField id="account_number_full" label="Full Account Number" error={fieldErrors.account_number_full}>
              <input id="account_number_full" name="account_number_full" type="password" value={accountNumber} onChange={(event) => setAccountNumber(event.target.value)} minLength={4} maxLength={34} inputMode="numeric" autoComplete="off" aria-invalid={Boolean(fieldErrors.account_number_full)} aria-describedby={fieldErrors.account_number_full ? 'account_number_full-error' : 'account-number-help'} className={inputClass} />
              <p id="account-number-help" className="mt-1 text-xs text-[#878787]">4–34 digits. Only the last four digits are displayed later.</p>
            </FormField>
            <FormField id="balance" label="Initial Balance" error={fieldErrors.balance}>
              <input id="balance" name="balance" type="number" value={balance} onChange={(event) => setBalance(event.target.value)} min="0" step="0.0001" inputMode="decimal" aria-invalid={Boolean(fieldErrors.balance)} aria-describedby={fieldErrors.balance ? 'balance-error' : undefined} className={inputClass} />
            </FormField>

            <div className="sm:col-span-2" aria-live="polite">
              {formError && <p role="alert" className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{formError}</p>}
              {successMessage && <p role="status" className="mb-4 rounded-md bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">{successMessage}</p>}
              <button type="submit" disabled={isLoading || Boolean(successMessage)} className="inline-flex min-h-12 w-full items-center justify-center rounded-md bg-[#299d91] px-6 py-3 font-bold text-white transition hover:bg-[#237f75] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto">
                {isLoading ? 'Adding account…' : 'Add Account'}
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}

const inputClass = 'mt-2 min-h-12 w-full rounded-md border border-[#d2d2d2] bg-white px-4 py-3 text-base outline-none transition focus:border-[#299d91] focus:ring-2 focus:ring-[#299d91]/20';

function FormField({ id, label, error, children }: { id: FieldName; label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-semibold text-[#333]">{label}</label>
      {children}
      {error && <p id={`${id}-error`} className="mt-1 text-sm text-red-700">{error}</p>}
    </div>
  );
}
