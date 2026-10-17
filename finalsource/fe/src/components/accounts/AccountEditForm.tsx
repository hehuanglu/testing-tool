import axios from 'axios';
import { useState, type FormEvent, type ReactNode } from 'react';
import { updateAccount, type BankAccount, type UpdateAccountInput } from '../../api/accounts';
import type { ApiError } from '../../api/types';

type FieldName = 'bank_name' | 'account_type' | 'branch_name' | 'account_number_full' | 'balance';
type FieldErrors = Partial<Record<FieldName, string>>;

const duplicateMessage = 'This account already exists in your list.';
const forbiddenMessage = 'You do not have permission to edit this account information.';
const systemMessage = 'An error occurred while saving data. Please try again later.';

function fieldForMessage(message: string): FieldName | null {
  if (message.includes('bank_name')) return 'bank_name';
  if (message.includes('account_type')) return 'account_type';
  if (message.includes('branch_name')) return 'branch_name';
  if (message.includes('account_number')) return 'account_number_full';
  if (message.includes('balance')) return 'balance';
  return null;
}

export function AccountEditForm({
  account,
  onCancel,
  onUpdated,
}: {
  account: BankAccount;
  onCancel: () => void;
  onUpdated: (account: BankAccount) => void;
}) {
  const [bankName, setBankName] = useState(account.bank_name);
  const [accountType, setAccountType] = useState(account.account_type);
  const [branchName, setBranchName] = useState(account.branch_name);
  const [replacementNumber, setReplacementNumber] = useState('');
  const [balance, setBalance] = useState(String(account.balance));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState('');
  const [toastMessage, setToastMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!bankName.trim()) errors.bank_name = 'Bank is required.';
    if (!accountType.trim()) errors.account_type = 'Account type is required.';
    if (replacementNumber.trim() && !/^[0-9]{4,34}$/.test(replacementNumber.trim())) {
      errors.account_number_full = 'Replacement account number must contain 4 to 34 digits.';
    }
    const balanceText = balance.trim();
    const numericBalance = Number(balanceText);
    if (
      !/^(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,4})?$/.test(balanceText) ||
      !Number.isFinite(numericBalance) ||
      numericBalance < 0 ||
      numericBalance > 999_999_999_999_999
    ) {
      errors.balance = 'Current balance must be between 0 and 999999999999999 with at most 4 decimal places.';
    }
    return errors;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isLoading) return;
    setFormError('');
    setToastMessage('');
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const input: UpdateAccountInput = {
      bank_name: bankName.trim(),
      account_type: accountType.trim(),
      branch_name: branchName.trim(),
      balance: Number(balance),
    };
    if (replacementNumber.trim()) input.account_number_full = replacementNumber.trim();

    setIsLoading(true);
    try {
      const result = await updateAccount(account.id, input);
      setReplacementNumber('');
      onUpdated({
        id: result.account.account_id,
        bank_name: result.account.bank_name,
        account_type: result.account.account_type,
        branch_name: result.account.branch_name,
        account_number_last_4: result.account.account_number_last_4,
        balance: result.account.balance,
      });
    } catch (error: unknown) {
      if (!axios.isAxiosError<ApiError>(error)) {
        setToastMessage(systemMessage);
        return;
      }
      const status = error.response?.status;
      const message = error.response?.data?.message;
      if (status === 400 && message) {
        const messages = Array.isArray(message) ? message : [message];
        const nextErrors: FieldErrors = {};
        for (const item of messages) {
          const field = fieldForMessage(item);
          if (field && !nextErrors[field]) nextErrors[field] = item;
        }
        setFieldErrors(nextErrors);
        if (Object.keys(nextErrors).length === 0) setFormError('Please correct the invalid account data.');
      } else if (status === 403) {
        setToastMessage(forbiddenMessage);
      } else if (status === 404) {
        setFormError('This account could not be found. Return to the account list and try again.');
      } else if (status === 409) {
        setFormError(duplicateMessage);
      } else {
        setToastMessage(systemMessage);
      }
    } finally {
      setIsLoading(false);
    }
  }

  function cancel(): void {
    setReplacementNumber('');
    onCancel();
  }

  return (
    <section className="rounded-xl bg-white p-6 shadow-[0_20px_40px_rgba(76,103,100,0.12)] sm:p-10" aria-labelledby="edit-account-title">
      <div className="mb-8">
        <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-[#299d91]">Account details</p>
        <h2 id="edit-account-title" className="text-3xl font-bold text-[#191919]">Edit {account.bank_name} Account</h2>
        <p className="mt-2 text-sm text-[#666]">Current account number ends in {account.account_number_last_4}. Enter a replacement only when it must change.</p>
      </div>

      {toastMessage && <p role="alert" className="mb-5 rounded-md bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{toastMessage}</p>}
      <form className="grid gap-6 sm:grid-cols-2" onSubmit={handleSubmit} noValidate>
        <FormField id="bank_name" label="Bank" error={fieldErrors.bank_name}>
          <input id="bank_name" name="bank_name" value={bankName} onChange={(event) => setBankName(event.target.value)} maxLength={160} autoComplete="organization" aria-invalid={Boolean(fieldErrors.bank_name)} aria-describedby={fieldErrors.bank_name ? 'bank_name-error' : undefined} className={inputClass} />
        </FormField>
        <FormField id="account_type" label="Account Type" error={fieldErrors.account_type}>
          <input id="account_type" name="account_type" value={accountType} onChange={(event) => setAccountType(event.target.value)} maxLength={64} autoComplete="off" aria-invalid={Boolean(fieldErrors.account_type)} aria-describedby={fieldErrors.account_type ? 'account_type-error' : undefined} className={inputClass} />
        </FormField>
        <FormField id="branch_name" label="Branch" error={fieldErrors.branch_name}>
          <input id="branch_name" name="branch_name" value={branchName} onChange={(event) => setBranchName(event.target.value)} maxLength={160} autoComplete="off" aria-invalid={Boolean(fieldErrors.branch_name)} aria-describedby={fieldErrors.branch_name ? 'branch_name-error' : undefined} className={inputClass} />
        </FormField>
        <FormField id="account_number_full" label="Full Account Number" error={fieldErrors.account_number_full}>
          <input id="account_number_full" name="account_number_full" type="password" value={replacementNumber} onChange={(event) => setReplacementNumber(event.target.value)} minLength={4} maxLength={34} inputMode="numeric" autoComplete="off" placeholder={`Leave blank to keep •••• ${account.account_number_last_4}`} aria-invalid={Boolean(fieldErrors.account_number_full)} aria-describedby={fieldErrors.account_number_full ? 'account_number_full-error' : 'replacement-number-help'} className={inputClass} />
          <p id="replacement-number-help" className="mt-1 text-xs text-[#878787]">Leave blank to keep the current number. A replacement must contain 4–34 digits.</p>
        </FormField>
        <FormField id="balance" label="Current Balance (VND)" error={fieldErrors.balance}>
          <input id="balance" name="balance" type="number" value={balance} onChange={(event) => setBalance(event.target.value)} min="0" max="999999999999999" step="0.0001" inputMode="decimal" aria-invalid={Boolean(fieldErrors.balance)} aria-describedby={fieldErrors.balance ? 'balance-error' : undefined} className={inputClass} />
        </FormField>

        <div className="sm:col-span-2" aria-live="polite">
          {formError && <p role="alert" className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{formError}</p>}
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" onClick={cancel} disabled={isLoading} className="min-h-12 rounded-md border border-[#299d91] px-6 py-3 font-bold text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">Cancel</button>
            <button type="submit" disabled={isLoading} className="inline-flex min-h-12 items-center justify-center rounded-md bg-[#299d91] px-6 py-3 font-bold text-white transition hover:bg-[#237f75] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">
              {isLoading ? <><span aria-hidden="true" className="mr-2 size-4 animate-spin rounded-full border-2 border-white border-t-transparent" />Saving changes…</> : 'Save Changes'}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}

const inputClass = 'mt-2 min-h-12 w-full rounded-md border border-[#d2d2d2] bg-white px-4 py-3 text-base outline-none transition focus:border-[#299d91] focus:ring-2 focus:ring-[#299d91]/20';

function FormField({ id, label, error, children }: { id: FieldName; label: string; error?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-semibold text-[#333]">{label}</label>
      {children}
      {error && <p id={`${id}-error`} className="mt-1 text-sm text-red-700">{error}</p>}
    </div>
  );
}
