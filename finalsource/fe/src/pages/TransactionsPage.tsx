import axios from 'axios';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { listTransactions, type Transaction, type TransactionFilter } from '../api/transactions';
import { useAuth } from '../context/auth-context';

const pageSize = 10;
const safeErrorMessage = 'Could not load transaction list. Please try again.';
const emptyMessage = 'You have no transactions recorded.';

function DashboardIcon({ children }: { children: ReactNode }) {
  return <span className="flex h-6 w-6 shrink-0 items-center justify-center" aria-hidden="true">{children}</span>;
}

function GridIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" /></svg>;
}

function WalletIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="17" height="14" rx="2"/><path d="M16 10h6v5h-6a2.5 2.5 0 0 1 0-5Z"/></svg>;
}

function TransferIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m7 7 3-3m0 0L7 1m3 3H3M17 17l-3 3m0 0 3 3m-3-3h7"/></svg>;
}

function ReceiptIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6"/></svg>;
}

function TargetIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/></svg>;
}

function SettingsIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><path d="M19 14.5l2-1.5-2-3-2.4.8a7 7 0 0 0-1.4-.8L15 7.5h-6L8.8 10a7 7 0 0 0-1.4.8L5 10l-2 3 2 1.5a7 7 0 0 0 0 1L3 17l2 3 2.4-.8a7 7 0 0 0 1.4.8L9 22.5h6l.2-2.5a7 7 0 0 0 1.4-.8l2.4.8 2-3-2-1.5a7 7 0 0 0 0-1Z"/></svg>;
}

function SearchIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></svg>;
}

function BellIcon() {
  return <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 22a2.5 2.5 0 0 0 2.35-1.65h-4.7A2.5 2.5 0 0 0 12 22Zm7-5-1.5-2V9a5.5 5.5 0 0 0-4.25-5.36V3a1.25 1.25 0 0 0-2.5 0v.64A5.5 5.5 0 0 0 6.5 9v6L5 17v1h14v-1Z"/></svg>;
}

function ItemIcon({ index }: { index: number }) {
  const paths = [
    <><rect key="a" x="3" y="7" width="18" height="11" rx="3"/><path key="b" d="m8 11-2 3m10-3 2 3M9 13h.01M15 13h.01M10 7l1-2h2l1 2"/></>,
    <><path key="a" d="M6 7h12v14H6zM9 7V5a3 3 0 0 1 6 0v2"/></>,
    <><path key="a" d="M5 9h14v11H5zM7 9l2-5h6l2 5M9 13h6M9 16h6"/></>,
    <><path key="a" d="M4 8h16v12H4zM4 8l2-4 2 4m4 0 2-4 2 4m4 0 2-4"/></>,
  ];
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-6 w-6">{paths[index % paths.length]}</svg>;
}

const navigation = [
  { label: 'Overview', icon: <GridIcon /> },
  { label: 'Balances', icon: <WalletIcon /> },
  { label: 'Transactions', icon: <TransferIcon />, selected: true },
  { label: 'Bills', icon: <ReceiptIcon /> },
  { label: 'Expenses', icon: <ReceiptIcon /> },
  { label: 'Goals', icon: <TargetIcon /> },
  { label: 'Settings', icon: <SettingsIcon /> },
];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date).replace(',', ',');
}

function formatAmount(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(value);
}

function TransactionSkeleton() {
  return (
    <div className="grid animate-pulse grid-cols-[1.25fr_1fr_.9fr_1fr_.55fr] items-center gap-6 border-b border-[#ececec] px-2 py-5 last:border-b-0" aria-hidden="true">
      {[44, 56, 48, 52, 32].map((width) => <span key={width} className="h-4 rounded bg-slate-200" style={{ width: `${width}%` }} />)}
    </div>
  );
}

export function TransactionsPage() {
  const { user, logout } = useAuth();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [activeTab, setActiveTab] = useState<TransactionFilter>('All');
  const [pagination, setPagination] = useState({ offset: 0, limit: pageSize, hasMore: false });
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const requestSequence = useRef(0);

  useEffect(() => {
    const message = sessionStorage.getItem('finebank.toast');
    if (message === 'Transaction added successfully.') {
      sessionStorage.removeItem('finebank.toast');
      setToast(message);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++requestSequence.current;
    setTransactions([]);
    setPagination({ offset: 0, limit: pageSize, hasMore: false });
    setError(null);
    setIsLoading(true);

    void listTransactions({ type: activeTab, limit: pageSize, offset: 0, signal: controller.signal })
      .then((result) => {
        if (requestSequence.current !== requestId) return;
        setTransactions(result.data);
        setPagination({ offset: result.data.length, limit: pageSize, hasMore: result.hasMore });
      })
      .catch((requestError: unknown) => {
        if (axios.isCancel(requestError) || requestSequence.current !== requestId) return;
        setError(safeErrorMessage);
      })
      .finally(() => {
        if (requestSequence.current === requestId) setIsLoading(false);
      });

    return () => controller.abort();
  }, [activeTab]);

  async function loadMore(): Promise<void> {
    if (isLoading || isLoadingMore || !pagination.hasMore) return;
    const requestId = ++requestSequence.current;
    setError(null);
    setIsLoadingMore(true);
    try {
      const result = await listTransactions({ type: activeTab, limit: pagination.limit, offset: pagination.offset });
      if (requestSequence.current !== requestId) return;
      setTransactions((current) => [...current, ...result.data]);
      setPagination((current) => ({ ...current, offset: current.offset + result.data.length, hasMore: result.hasMore }));
    } catch {
      if (requestSequence.current === requestId) setError(safeErrorMessage);
    } finally {
      if (requestSequence.current === requestId) setIsLoadingMore(false);
    }
  }

  const tabs: Array<{ label: string; value: TransactionFilter }> = [
    { label: 'All', value: 'All' },
    { label: 'Revenue', value: 'Revenue' },
    { label: 'Expenses', value: 'Expense' },
  ];

  return (
    <div className="min-h-screen bg-[#f4f5f7] text-[#1b1b1b] lg:grid lg:grid-cols-[280px_1fr]">
      <aside className="flex min-h-screen flex-col bg-[#191919] px-7 py-10 text-[#b9b9b9]">
        <div className="px-7 text-[25px] font-bold tracking-[1.5px] text-white">FINEbank.IO</div>
        <nav aria-label="Primary" className="mt-11 space-y-3">
          {navigation.map((item) => (
            item.label === 'Balances' ? (
              <Link key={item.label} to="/accounts" className="flex h-12 items-center gap-3 rounded px-4 text-[16px] focus:outline-none focus:ring-2 focus:ring-[#2fa597]">
                <DashboardIcon>{item.icon}</DashboardIcon><span>{item.label}</span>
              </Link>
            ) : (
              <div key={item.label} aria-current={item.selected ? 'page' : undefined} className={`flex h-12 items-center gap-3 rounded px-4 text-[16px] ${item.selected ? 'bg-[#2fa597] font-semibold text-white' : ''}`}>
                <DashboardIcon>{item.icon}</DashboardIcon><span>{item.label}</span>
              </div>
            )
          ))}
        </nav>
        <div className="mt-auto">
          <button type="button" onClick={logout} className="flex h-12 w-full items-center gap-3 rounded bg-[#252525] px-4 text-left font-semibold text-[#c8c8c8] focus:outline-none focus:ring-2 focus:ring-[#2fa597]">
            <DashboardIcon><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M10 5H5v14h5M14 8l4 4-4 4M18 12H8"/></svg></DashboardIcon>
            Logout
          </button>
          <div className="mt-11 flex items-center border-t border-[#303030] pt-8">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#38413f] text-sm font-semibold text-white">{(user?.fullName ?? 'Tanzir Rahman').slice(0, 1)}</div>
            <div className="ml-3 min-w-0"><p className="truncate text-sm font-semibold text-white">{user?.fullName ?? 'Tanzir Rahman'}</p><p className="text-xs">View profile</p></div>
            <span className="ml-auto text-xl text-white" aria-hidden="true">⋮</span>
          </div>
        </div>
      </aside>

      <main className="min-w-0">
        <header className="flex h-[88px] items-center border-b border-[#e4e4e4] px-7 lg:px-12">
          <span className="text-[#9b9b9b]"><span className="mr-2 text-2xl">»</span>May 19, 2023</span>
          <div className="ml-auto flex items-center gap-10">
            <span className="relative h-6 w-6 text-[#6c6c6c]"><BellIcon /><span className="absolute right-0 top-0 h-2 w-2 rounded-full bg-[#2fa597] ring-2 ring-[#f4f5f7]" /></span>
            <label className="flex h-12 w-[352px] items-center rounded-2xl bg-white px-8 text-[#a5a5a5] shadow-[0_16px_30px_rgba(44,52,68,0.08)]">
              <span className="sr-only">Search</span><input readOnly value="" placeholder="Search here" className="w-full bg-transparent outline-none placeholder:text-[#a5a5a5]" />
              <span className="h-6 w-6 text-[#505050]"><SearchIcon /></span>
            </label>
          </div>
        </header>

        <section className="px-6 pb-20 pt-5 lg:px-12" aria-labelledby="transactions-heading">
          <div className="flex items-center justify-between gap-4"><h1 id="transactions-heading" className="text-[24px] font-normal text-[#8b8b8b]">Recent Transaction</h1><Link to="/transactions/new" className="rounded-xl bg-[#2fa597] px-5 py-3 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#2fa597] focus:ring-offset-2">Add transaction</Link></div>
          {toast && <div role="status" className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{toast}</div>}
          <div className="mt-5 flex gap-9" role="tablist" aria-label="Transaction type">
            {tabs.map((tab) => (
              <button key={tab.value} type="button" role="tab" aria-selected={activeTab === tab.value} onClick={() => setActiveTab(tab.value)} className={`border-b-2 px-2 pb-2 text-[16px] font-semibold focus:outline-none focus:ring-2 focus:ring-[#2fa597] focus:ring-offset-2 ${activeTab === tab.value ? 'border-[#2fa597] text-[#2fa597]' : 'border-transparent text-[#555]'}`}>
                {tab.label}
              </button>
            ))}
          </div>

          <div className="mt-4 min-h-[704px] rounded-[18px] bg-white px-7 pb-14 pt-2 shadow-[0_18px_35px_rgba(33,43,54,0.08)]">
            <div className="grid grid-cols-[1.25fr_1fr_.9fr_1fr_.55fr] gap-6 border-b border-[#ececec] px-2 py-5 text-[15px] font-bold">
              <span>Items</span><span>Shop Name</span><span>Date</span><span>Payment Method</span><span className="text-right">Amount</span>
            </div>

            {isLoading ? (
              <div aria-label="Loading transactions">{Array.from({ length: 7 }, (_, index) => <TransactionSkeleton key={index} />)}</div>
            ) : error ? (
              <div className="flex min-h-[420px] items-center justify-center text-center text-[#666]" role="alert">{error}</div>
            ) : transactions.length === 0 ? (
              <div className="flex min-h-[420px] items-center justify-center text-center text-[#666]">{emptyMessage}</div>
            ) : (
              <>
                <div>
                  {transactions.map((transaction, index) => (
                    <div key={transaction.transactionId} className="grid grid-cols-[1.25fr_1fr_.9fr_1fr_.55fr] items-center gap-6 border-b border-[#ececec] px-2 py-[23px] last:border-b-0">
                      <div className="flex min-w-0 items-center gap-4 font-semibold"><span className="text-[#565656]"><ItemIcon index={index} /></span><span className="truncate">{transaction.itemDescription}</span></div>
                      <span className="truncate text-[#666]">{transaction.shopName}</span>
                      <span className="text-[#666]">{formatDate(transaction.transactionDate)}</span>
                      <span className="truncate text-[#666]">{transaction.paymentMethod}</span>
                      <span className="text-right font-semibold">{formatAmount(transaction.amount)}</span>
                    </div>
                  ))}
                </div>
                {pagination.hasMore && (
                  <div className="mt-7 flex justify-center">
                    <button type="button" disabled={isLoadingMore} onClick={() => { void loadMore(); }} className="h-12 min-w-48 rounded bg-[#2fa597] px-8 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#2fa597] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">
                      {isLoadingMore ? 'Loading…' : 'Load More'}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
