import axios from 'axios';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getAccountDetails, type AccountDetail, type BankAccount } from '../api/accounts';
import { AccountEditForm } from '../components/accounts/AccountEditForm';
import { DeleteAccountModal } from '../components/accounts/DeleteAccountModal';
import { useAuth } from '../context/auth-context';
import imgProfile from '../assets/accounts/asset-005.png';
import imgChevronsRight from '../assets/accounts/asset-007.svg';
import imgNotification from '../assets/accounts/asset-008.svg';

const forbiddenMessage = 'You do not have permission to view this account information.';
const notFoundMessage = 'This account was not found.';
const genericMessage = 'An error occurred, data could not be loaded.';

function asBankAccount(account: AccountDetail): BankAccount {
  return {
    id: account.id,
    bank_name: account.bank_name,
    account_type: account.account_type,
    branch_name: account.branch_name,
    account_number_last_4: account.account_number_last_4,
    balance: account.balance,
  };
}

function formatMoney(value: number): string {
  return `${value < 0 ? '-' : ''}$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Math.abs(value))}`;
}

function formatDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.valueOf()) ? value : new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(parsed);
}

export function AccountDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [accountData, setAccountData] = useState<AccountDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const accountId = Number(id);
    if (!Number.isSafeInteger(accountId) || accountId <= 0) {
      navigate('/accounts', { replace: true, state: { message: notFoundMessage } });
      return;
    }

    const controller = new AbortController();
    let active = true;
    setAccountData(null);
    setError(null);
    setIsLoading(true);

    async function fetchAccountDetails(): Promise<void> {
      try {
        const result = await getAccountDetails(accountId, controller.signal);
        if (active) {
          setAccountData(result);
          setError(null);
        }
      } catch (failure: unknown) {
        if (!active || axios.isCancel(failure)) return;
        if (axios.isAxiosError(failure)) {
          if (failure.response?.status === 401) {
            logout();
            navigate('/login', { replace: true, state: { sessionMessage: 'Please log in again.' } });
            return;
          }
          if (failure.response?.status === 404) {
            navigate('/accounts', { replace: true, state: { message: notFoundMessage } });
            return;
          }
          if (failure.response?.status === 403) {
            setError(forbiddenMessage);
            return;
          }
        }
        setError(genericMessage);
      } finally {
        if (active) setIsLoading(false);
      }
    }

    void fetchAccountDetails();
    return () => {
      active = false;
      controller.abort();
    };
  }, [id, logout, navigate]);

  return (
    <div className="min-h-screen bg-[#f4f5f7] text-[#191919] lg:min-h-[1024px]" data-node-id="416:7878" data-name="106. Account Details">
      <AccountSidebar fullName={user?.fullName ?? 'Application user'} onLogout={() => { logout(); navigate('/login', { replace: true }); }} />
      <AccountHeader />
      <main className="px-4 pb-16 pt-24 sm:px-6 lg:ml-[280px] lg:px-6 lg:pb-[88px] lg:pt-[104px] xl:px-6">
        <div className="mx-auto max-w-[1104px]">
          <h1 className="mb-4 text-[22px] font-normal leading-8 text-[#878787]">Account Details</h1>
          {isLoading ? <AccountDetailSkeleton /> : error ? (
            <section role="alert" className="rounded-lg bg-white p-8 shadow-[0_20px_40px_rgba(76,103,100,0.10)]">
              <p className="font-medium text-red-700">{error}</p>
              <Link to="/accounts" className="mt-6 inline-flex rounded bg-[#299d91] px-5 py-3 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2">Back to accounts</Link>
            </section>
          ) : accountData ? (
            <>
              {isEditing ? (
                <AccountEditForm
                  account={asBankAccount(accountData)}
                  onCancel={() => setIsEditing(false)}
                  onUpdated={(updated) => {
                    setAccountData((current) => current ? { ...current, ...updated } : current);
                    setIsEditing(false);
                  }}
                />
              ) : (
                <AccountSummary account={accountData} onEdit={() => setIsEditing(true)} onRemove={() => setIsDeleting(true)} />
              )}
              <TransactionHistory account={accountData} />
            </>
          ) : null}
        </div>
      </main>
      {isDeleting && accountData && (
        <DeleteAccountModal
          account={asBankAccount(accountData)}
          onCancel={() => setIsDeleting(false)}
          onUnauthorized={() => { setIsDeleting(false); logout(); navigate('/login', { replace: true, state: { sessionMessage: 'Please log in again.' } }); }}
          onDeleted={() => navigate('/accounts', { replace: true, state: { message: 'Account successfully deleted.' } })}
        />
      )}
    </div>
  );
}

function AccountSummary({ account, onEdit, onRemove }: { account: AccountDetail; onEdit: () => void; onRemove: () => void }) {
  return (
    <section className="rounded-lg bg-white px-8 py-9 shadow-[0_20px_40px_rgba(76,103,100,0.10)] lg:min-h-[293px]" aria-labelledby="account-summary-title">
      <h2 id="account-summary-title" className="sr-only">Account summary</h2>
      <dl className="grid gap-x-16 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
        <Detail label="Bank Name" value={account.bank_name} />
        <Detail label="Account Type" value={account.account_type} />
        <Detail label="Balance" value={formatMoney(account.balance)} />
        <Detail label="Branch Name" value={account.branch_name || '—'} />
        <Detail label="Account Number" value={`•••• •••• •••• ${account.account_number_last_4}`} />
      </dl>
      <div className="mt-9 flex items-center gap-10">
        <button type="button" onClick={onEdit} className="rounded bg-[#299d91] px-9 py-3 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2">Edit Details</button>
        <button type="button" onClick={onRemove} className="rounded px-1 py-3 font-medium text-[#666] focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2">Remove</button>
      </div>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-base font-normal text-[#9f9f9f]">{label}</dt><dd className="mt-1 text-xl font-semibold text-[#525256]">{value}</dd></div>;
}

function TransactionHistory({ account }: { account: AccountDetail }) {
  return (
    <section className="mt-8" aria-labelledby="transactions-history-title">
      <h2 id="transactions-history-title" className="mb-4 text-[22px] font-normal leading-8 text-[#878787]">Transactions History</h2>
      <div className="overflow-x-auto rounded-2xl bg-white px-8 pb-10 pt-5 shadow-[0_20px_40px_rgba(76,103,100,0.10)] lg:min-h-[412px]">
        {account.recent_transactions.length === 0 ? (
          <p className="py-16 text-center text-[#666]">No transactions have been recorded for this account.</p>
        ) : (
          <table className="w-full min-w-[980px] table-fixed text-left">
            <caption className="sr-only">Five most recent transactions for {account.bank_name}</caption>
            <thead><tr className="border-b border-[#ededed] text-base font-semibold">
              <th className="w-[14%] py-4">Date</th><th className="w-[18%] py-4">Description</th><th className="w-[13%] py-4">Status</th><th className="w-[16%] py-4">Transaction Type</th><th className="w-[19%] py-4">Receipt</th><th className="w-[20%] py-4 text-right">Amount</th>
            </tr></thead>
            <tbody>{account.recent_transactions.map((transaction, index) => (
              <tr key={`${transaction.date}-${transaction.receipt_id ?? 'none'}-${index}`} className="border-b border-[#ededed] text-base text-[#666] last:border-b-0">
                <td className="py-4">{formatDate(transaction.date)}</td><td className="truncate py-4 pr-4" title={transaction.description}>{transaction.description}</td><td className="py-4">{transaction.status}</td><td className="py-4">{transaction.type}</td><td className="py-4">{transaction.receipt_id ?? '—'}</td><td className={`py-4 text-right font-semibold ${transaction.amount < 0 ? 'text-red-700' : 'text-[#191919]'}`}>{formatMoney(transaction.amount)}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
        <div className="mt-7 flex justify-center"><button type="button" disabled aria-disabled="true" title="Only the five most recent transactions are available" className="cursor-not-allowed rounded bg-[#299d91] px-14 py-3 font-semibold text-white opacity-100 focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2">Load More</button></div>
      </div>
    </section>
  );
}

function AccountHeader() {
  return (
    <header className="border-b border-[#e8e8e8] bg-[#f4f5f7] px-5 py-5 lg:ml-[280px] lg:h-[88px] lg:px-6" aria-label="Account utilities">
      <div className="mx-auto flex max-w-[1104px] items-center justify-between">
        <div className="flex items-center gap-1 text-sm text-[#9f9f9f]"><img src={imgChevronsRight} alt="" className="h-6 w-6" /><span>May 19, 2023</span></div>
        <div className="flex items-center gap-10"><img src={imgNotification} alt="Notifications" className="h-6 w-6" /><div className="flex h-12 w-[352px] items-center justify-between rounded-xl bg-white px-8 text-[#9f9f9f] shadow-[0_26px_13px_rgba(106,22,58,0.04)]"><span>Search here</span><span aria-hidden="true" className="text-2xl text-[#555]">⌕</span></div></div>
      </div>
    </header>
  );
}

function AccountSidebar({ fullName, onLogout }: { fullName: string; onLogout: () => void }) {
  const items = ['Overview', 'Balances', 'Transactions', 'Bills', 'Expenses', 'Goals', 'Settings'];
  return (
    <aside className="hidden bg-[#191919] px-7 py-12 text-white lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-[280px] lg:flex-col" aria-label="Application sidebar">
      <Link to="/accounts" className="text-center font-['Poppins',sans-serif] text-2xl font-semibold tracking-[1.92px] focus:outline-none focus:ring-2 focus:ring-white">FINEbank.IO</Link>
      <nav className="mt-10 flex flex-col gap-4" aria-label="Primary">
        {items.map((item) => item === 'Balances' ? <Link key={item} to="/accounts" aria-current="page" className="flex h-12 items-center gap-3 rounded bg-[#299d91] px-4 font-semibold"><span aria-hidden="true">▣</span>{item}</Link> : item === 'Transactions' ? <Link key={item} to="/transactions" className="flex h-12 items-center gap-3 rounded px-4 text-white/70 focus:outline-none focus:ring-2 focus:ring-white"><span aria-hidden="true">⇄</span>{item}</Link> : <span key={item} aria-disabled="true" className="flex h-12 items-center gap-3 rounded px-4 text-white/70"><span aria-hidden="true">◇</span>{item}</span>)}
      </nav>
      <div className="mt-auto">
        <button type="button" onClick={onLogout} className="flex h-12 w-full items-center gap-3 rounded bg-white/10 px-4 font-semibold text-white/80 focus:outline-none focus:ring-2 focus:ring-white"><span aria-hidden="true">↪</span>Logout</button>
        <div className="mt-11 flex items-center gap-4 border-t border-white/10 py-8"><img src={imgProfile} alt="" className="h-8 w-8 rounded-full" /><div className="min-w-0"><p className="truncate font-semibold">{fullName}</p><p className="text-xs text-white/70">View profile</p></div><span className="ml-auto" aria-hidden="true">⋮</span></div>
      </div>
    </aside>
  );
}

function AccountDetailSkeleton() {
  return <div role="status" aria-label="Loading account details" aria-busy="true" className="animate-pulse motion-reduce:animate-none"><div className="h-[293px] rounded-lg bg-white shadow-[0_20px_40px_rgba(76,103,100,0.10)]"/><div className="mt-8 h-8 w-56 rounded bg-[#e2e4e7]"/><div className="mt-4 h-[412px] rounded-2xl bg-white shadow-[0_20px_40px_rgba(76,103,100,0.10)]"/></div>;
}
