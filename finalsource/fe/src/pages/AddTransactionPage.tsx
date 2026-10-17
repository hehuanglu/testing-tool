import axios from 'axios';
import { useEffect, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createTransaction,
  listAccountOptions,
  listCategoryOptions,
  type AccountOption,
  type CategoryOption,
  type TransactionType,
} from '../api/transactions';

interface FormState {
  itemDescription: string;
  categoryId: string;
  amount: string;
  type: TransactionType;
  accountId: string;
  transactionDate: string;
  shopName: string;
  paymentMethod: string;
  status: string;
}

type FieldErrors = Partial<Record<keyof FormState, string>>;

const initialForm: FormState = {
  itemDescription: '',
  categoryId: '',
  amount: '',
  type: 'Expense',
  accountId: '',
  transactionDate: '',
  shopName: '',
  paymentMethod: '',
  status: 'Complete',
};

const submitErrorMessage = 'Cannot add transaction at this time. Please try again later.';
const optionsErrorMessage = 'Account and category choices are unavailable. Please try again later.';

function validate(form: FormState): FieldErrors {
  const errors: FieldErrors = {};
  if (!form.itemDescription.trim()) errors.itemDescription = 'Transaction name is required.';
  if (!form.categoryId) errors.categoryId = 'Category is required.';
  if (!form.accountId) errors.accountId = 'Payment account is required.';
  if (!form.transactionDate) errors.transactionDate = 'Transaction date is required.';
  if (!form.shopName.trim()) errors.shopName = 'Shop name is required.';
  if (!form.paymentMethod.trim()) errors.paymentMethod = 'Payment method is required.';
  if (!/^(?!0+(?:\.0+)?$)(?:0|[1-9]\d{0,14})(?:\.\d{1,4})?$/.test(form.amount)) errors.amount = 'Amount must be greater than zero with up to four decimal places.';
  return errors;
}

export function AddTransactionPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>(initialForm);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [isOptionsLoading, setIsOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setIsOptionsLoading(true);
    setOptionsError(null);
    void Promise.all([listAccountOptions(controller.signal), listCategoryOptions(controller.signal)])
      .then(([accountOptions, categoryOptions]) => {
        setAccounts(accountOptions);
        setCategories(categoryOptions);
        if (accountOptions.length === 0 || categoryOptions.length === 0) setOptionsError(optionsErrorMessage);
      })
      .catch((error: unknown) => {
        if (!axios.isCancel(error)) setOptionsError(optionsErrorMessage);
      })
      .finally(() => setIsOptionsLoading(false));
    return () => controller.abort();
  }, []);

  function updateField(event: ChangeEvent<HTMLInputElement | HTMLSelectElement>): void {
    const key = event.target.name as keyof FormState;
    const value = event.target.value;
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isLoading || isOptionsLoading || optionsError) return;
    const nextErrors = validate(form);
    setErrors(nextErrors);
    setSubmitError(null);
    if (Object.keys(nextErrors).length > 0) return;

    setIsLoading(true);
    try {
      await createTransaction({
        accountId: Number(form.accountId),
        transactionDate: new Date(`${form.transactionDate}T00:00:00.000Z`).toISOString(),
        type: form.type,
        itemDescription: form.itemDescription.trim(),
        category_id: Number(form.categoryId),
        shopName: form.shopName.trim(),
        amount: form.amount,
        paymentMethod: form.paymentMethod.trim(),
        status: form.status,
      });
      setForm(initialForm);
      sessionStorage.setItem('finebank.toast', 'Transaction added successfully.');
      navigate('/transactions');
    } catch {
      setSubmitError(submitErrorMessage);
    } finally {
      setIsLoading(false);
    }
  }

  const saveDisabled = isLoading || isOptionsLoading || Boolean(optionsError);
  const inputClass = 'mt-2 h-12 w-full rounded-xl border border-[#dfe3e8] bg-white px-4 text-[#252525] outline-none transition focus:border-[#299d91] focus:ring-2 focus:ring-[#299d91]/20 disabled:bg-slate-100';

  return (
    <main className="min-h-screen bg-[#f4f5f7] px-4 py-10 text-[#252525] sm:px-8">
      <section className="mx-auto max-w-3xl rounded-[18px] bg-white p-6 shadow-[0_18px_35px_rgba(33,43,54,0.08)] sm:p-10" aria-labelledby="add-transaction-heading">
        <div className="flex items-center justify-between gap-4">
          <div><p className="text-sm font-semibold text-[#299d91]">Transactions</p><h1 id="add-transaction-heading" className="mt-1 text-2xl font-semibold">Add transaction</h1></div>
          <button type="button" onClick={() => navigate('/transactions')} className="rounded-lg px-4 py-2 font-semibold text-[#555] focus:outline-none focus:ring-2 focus:ring-[#299d91]">Cancel</button>
        </div>

        {optionsError && <div role="alert" className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{optionsError}</div>}
        {submitError && <div role="alert" className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{submitError}</div>}

        <form className="mt-8 space-y-5" onSubmit={(event) => { void handleSubmit(event); }} noValidate>
          <Field label="Transaction Name / Item Description" error={errors.itemDescription}>
            <input className={inputClass} id="itemDescription" name="itemDescription" value={form.itemDescription} onChange={updateField} disabled={isLoading} maxLength={255} />
          </Field>

          <Field label="Category" error={errors.categoryId}>
            <select className={inputClass} id="categoryId" name="categoryId" value={form.categoryId} onChange={updateField} disabled={isLoading || isOptionsLoading}>
              <option value="">Select a category</option>
              {categories.map((category) => <option key={category.category_id} value={category.category_id}>{category.name}</option>)}
            </select>
          </Field>

          <Field label="Amount" error={errors.amount}>
            <input className={inputClass} id="amount" name="amount" value={form.amount} onChange={updateField} disabled={isLoading} inputMode="decimal" placeholder="0.00" />
          </Field>

          <Field label="Transaction Type" error={errors.type}>
            <select className={inputClass} id="type" name="type" value={form.type} onChange={updateField} disabled={isLoading}>
              <option value="Revenue">Revenue</option><option value="Expense">Expense</option>
            </select>
          </Field>

          <Field label="Payment Account" error={errors.accountId}>
            <select className={inputClass} id="accountId" name="accountId" value={form.accountId} onChange={updateField} disabled={isLoading || isOptionsLoading}>
              <option value="">Select an account</option>
              {accounts.map((account) => <option key={account.accountId} value={account.accountId}>Account #{account.accountId}</option>)}
            </select>
          </Field>

          <Field label="Transaction Date" error={errors.transactionDate}>
            <input className={inputClass} id="transactionDate" name="transactionDate" type="date" value={form.transactionDate} onChange={updateField} disabled={isLoading} />
          </Field>

          <Field label="Shop Name" error={errors.shopName}>
            <input className={inputClass} id="shopName" name="shopName" value={form.shopName} onChange={updateField} disabled={isLoading} maxLength={160} />
          </Field>

          <Field label="Payment Method" error={errors.paymentMethod}>
            <input className={inputClass} id="paymentMethod" name="paymentMethod" value={form.paymentMethod} onChange={updateField} disabled={isLoading} maxLength={64} />
          </Field>

          <Field label="Status" error={errors.status}>
            <select className={inputClass} id="status" name="status" value={form.status} onChange={updateField} disabled={isLoading}><option value="Complete">Complete</option></select>
          </Field>

          <div className="flex flex-col-reverse gap-3 pt-3 sm:flex-row sm:justify-end">
            <button type="button" onClick={() => navigate('/transactions')} disabled={isLoading} className="h-12 rounded-xl border border-[#dfe3e8] px-7 font-semibold text-[#555] focus:outline-none focus:ring-2 focus:ring-[#299d91] disabled:opacity-60">Cancel</button>
            <button type="submit" disabled={saveDisabled} className="h-12 min-w-36 rounded-xl bg-[#299d91] px-7 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">
              {isLoading ? <span className="inline-flex items-center gap-2"><span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" aria-hidden="true" />Saving…</span> : 'Save'}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  const id = label === 'Transaction Name / Item Description' ? 'itemDescription' : label.replaceAll(' ', '').replace('PaymentAccount', 'accountId').replace('TransactionDate', 'transactionDate').replace('TransactionType', 'type').replace('ShopName', 'shopName').replace('PaymentMethod', 'paymentMethod').replace('Category', 'categoryId').replace('Amount', 'amount').replace('Status', 'status');
  return <div><label htmlFor={id} className="text-sm font-semibold text-[#444]">{label}</label>{children}{error && <p className="mt-1 text-sm text-red-600">{error}</p>}</div>;
}
