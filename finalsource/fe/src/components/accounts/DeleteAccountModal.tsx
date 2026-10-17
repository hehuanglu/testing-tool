import axios from 'axios';
import { useEffect, useRef, useState } from 'react';
import { deleteAccount, type BankAccount } from '../../api/accounts';
import type { ApiError } from '../../api/types';

interface DeleteAccountModalProps {
  readonly account: BankAccount;
  readonly onCancel: () => void;
  readonly onDeleted: (deletedAccountId: number) => void;
  readonly onUnauthorized: () => void;
}

const safeSystemError = 'A system error has occurred, please try again later.';

function safeApiMessage(failure: unknown): string {
  if (!axios.isAxiosError<ApiError>(failure)) return safeSystemError;
  const message = failure.response?.data?.message;
  if (typeof message === 'string') return message;
  if (Array.isArray(message) && message.every((item) => typeof item === 'string')) return message.join('. ');
  return safeSystemError;
}

export function DeleteAccountModal({ account, onCancel, onDeleted, onUnauthorized }: DeleteAccountModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isLoading) dialogRef.current?.focus();
    else cancelRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isLoading) {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== 'Tab') return;
      const controls = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled)') ?? []);
      if (controls.length === 0) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isLoading, onCancel]);

  async function handleDeleteAccount(): Promise<void> {
    if (!Number.isSafeInteger(account.id) || account.id <= 0 || isLoading) return;
    setError(null);
    setIsLoading(true);
    try {
      const result = await deleteAccount(account.id);
      if (result.deleted_account_id !== account.id) throw new Error('Unexpected deleted account identifier');
      onDeleted(result.deleted_account_id);
    } catch (failure: unknown) {
      if (axios.isAxiosError(failure) && failure.response?.status === 401) {
        onUnauthorized();
        return;
      }
      setError(safeApiMessage(failure));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4" role="presentation">
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="delete-account-title" aria-describedby="delete-account-warning" tabIndex={-1} className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl focus:outline-none">
        <div className="flex items-start gap-4">
          <div aria-hidden="true" className="motion-safe:animate-pulse flex size-12 shrink-0 items-center justify-center rounded-full bg-red-100 text-2xl text-red-700">!</div>
          <div>
            <h2 id="delete-account-title" className="text-xl font-bold text-[#191919]">Account Deletion Confirmation</h2>
            <p id="delete-account-warning" className="mt-3 text-sm leading-6 text-[#666]">
              <strong className="text-red-700">WARNING:</strong> Are you sure you want to delete account {account.bank_name} - [**** {account.account_number_last_4}]? This action will <strong className="text-red-700">PERMANENTLY</strong> delete the account and <strong className="text-red-700">ALL</strong> related transactions.
            </p>
          </div>
        </div>
        {error && <p role="alert" className="mt-5 rounded-md bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={isLoading} className="min-h-11 rounded-md border border-[#d2d2d2] px-5 py-2 font-semibold text-[#666] hover:bg-[#f4f5f7] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">Cancel</button>
          <button type="button" onClick={() => void handleDeleteAccount()} disabled={isLoading} className="inline-flex min-h-11 min-w-40 items-center justify-center gap-2 rounded-md bg-red-700 px-5 py-2 font-semibold text-white hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">
            {isLoading && <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
            {isLoading ? 'Deleting…' : 'Confirm Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}
