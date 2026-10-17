import axios from 'axios';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getExpenseBreakdown, getExpenseSummary, type ExpenseBreakdownCategory, type MonthlyExpense } from '../api/expenses';
import profileImage from '../assets/accounts/asset-005.png';
import { useAuth } from '../context/auth-context';

const safeErrorMessage = 'Cannot load data for Expense.';
const emptyMessage = 'No spending data has been recorded for analysis.';
const breakdownEmptyMessage = 'You have no expenses recorded this month.';
const breakdownErrorMessage = 'Cannot load expense details right now.';
const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;

function Icon({ children }: { children: ReactNode }) {
  return <span className="flex h-6 w-6 items-center justify-center" aria-hidden="true">{children}</span>;
}

const navigation = ['Overview', 'Balances', 'Transactions', 'Bills', 'Expenses', 'Goals', 'Settings'];
function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
}

function currentMonthValue(): string {
  const now = new Date();
  return `${now.getFullYear().toString().padStart(4, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function formatTransactionDate(value: string): string {
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00.000Z`));
}

function categoryIcon(category: string): string {
  const icons: Readonly<Record<string, string>> = { Housing: '⌂', Food: '♜', Transportation: '▤', Entertainment: '⌁', Shopping: '▢', Others: '▦' };
  return icons[category] ?? '▧';
}

export function ExpenseSummaryPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const requestSequence = useRef(0);
  const breakdownRequestSequence = useRef(0);
  const [summaryData, setSummaryData] = useState<MonthlyExpense[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState(currentMonthValue);
  const [expensesData, setExpensesData] = useState<ExpenseBreakdownCategory[]>([]);
  const [isBreakdownLoading, setIsBreakdownLoading] = useState(true);
  const [breakdownError, setBreakdownError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++requestSequence.current;
    setSummaryData([]);
    setError(null);
    setIsLoading(true);

    void getExpenseSummary(controller.signal)
      .then((result) => {
        if (requestSequence.current !== requestId) return;
        setSummaryData(result.data);
      })
      .catch((failure: unknown) => {
        if (axios.isCancel(failure) || requestSequence.current !== requestId) return;
        if (axios.isAxiosError(failure) && failure.response?.status === 401) {
          logout();
          navigate('/login', { replace: true, state: { sessionMessage: 'Please log in again.' } });
          return;
        }
        setError(safeErrorMessage);
      })
      .finally(() => {
        if (requestSequence.current === requestId) setIsLoading(false);
      });

    return () => controller.abort();
  }, [logout, navigate]);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++breakdownRequestSequence.current;
    setExpensesData([]);
    setBreakdownError(null);
    setIsBreakdownLoading(true);

    void getExpenseBreakdown(selectedMonth, controller.signal)
      .then((result) => {
        if (breakdownRequestSequence.current === requestId) setExpensesData(result.data);
      })
      .catch((failure: unknown) => {
        if (axios.isCancel(failure) || breakdownRequestSequence.current !== requestId) return;
        setExpensesData([]);
        if (axios.isAxiosError(failure) && failure.response?.status === 401) {
          logout();
          navigate('/login', { replace: true, state: { sessionMessage: 'Please log in again.' } });
          return;
        }
        setBreakdownError(axios.isAxiosError(failure) && failure.response?.status === 404 ? breakdownEmptyMessage : breakdownErrorMessage);
      })
      .finally(() => {
        if (breakdownRequestSequence.current === requestId) setIsBreakdownLoading(false);
      });

    return () => controller.abort();
  }, [logout, navigate, selectedMonth]);

  const currentMonth = monthNames[new Date().getMonth()];

  return (
    <div className="min-h-screen bg-[#f4f5f7] text-[#1b1b1b] lg:grid lg:min-h-[1024px] lg:grid-cols-[280px_1fr]" data-node-id="66:5698" data-name="109. Expenses">
      <aside className="flex min-h-screen flex-col bg-[#191919] px-7 py-10 text-[#b9b9b9]" aria-label="Application sidebar">
        <Link to="/" className="px-7 text-[25px] font-bold tracking-[1.5px] text-white focus:outline-none focus:ring-2 focus:ring-[#2fa597]">FINEbank.IO</Link>
        <nav aria-label="Primary" className="mt-11 space-y-3">
          {navigation.map((item) => {
            const link = item === 'Balances' ? '/accounts' : item === 'Transactions' ? '/transactions' : item === 'Expenses' ? '/expenses' : undefined;
            const content = <><Icon>{item === 'Expenses' ? '▣' : '◇'}</Icon><span>{item}</span></>;
            const className = `flex h-12 items-center gap-3 rounded px-4 text-[16px] focus:outline-none focus:ring-2 focus:ring-[#2fa597] ${item === 'Expenses' ? 'bg-[#2fa597] font-semibold text-white' : ''}`;
            return link ? <Link key={item} to={link} aria-current={item === 'Expenses' ? 'page' : undefined} className={className}>{content}</Link> : <span key={item} aria-disabled="true" className={className}>{content}</span>;
          })}
        </nav>
        <div className="mt-auto">
          <button type="button" onClick={() => { logout(); navigate('/login', { replace: true }); }} className="flex h-12 w-full items-center gap-3 rounded bg-[#252525] px-4 font-semibold text-[#c8c8c8] focus:outline-none focus:ring-2 focus:ring-[#2fa597]"><Icon>↪</Icon>Logout</button>
          <div className="mt-11 flex items-center border-t border-[#303030] pt-8"><img src={profileImage} alt="" className="h-9 w-9 rounded-full object-cover" /><div className="ml-3 min-w-0"><p className="truncate text-sm font-semibold text-white">{user?.fullName ?? 'Application user'}</p><p className="text-xs">View profile</p></div><span className="ml-auto text-xl text-white" aria-hidden="true">⋮</span></div>
        </div>
      </aside>

      <main className="min-w-0">
        <header className="flex h-[88px] items-center border-b border-[#e4e4e4] px-6 lg:px-12" aria-label="Page utilities">
          <span className="text-[#9b9b9b]"><span className="mr-2 text-2xl">»</span>May 19, 2023</span>
          <div className="ml-auto flex items-center gap-10"><span className="relative text-2xl text-[#6c6c6c]" aria-label="Notifications">♟<span className="absolute right-0 top-0 h-2 w-2 rounded-full bg-[#2fa597]" /></span><label className="hidden h-12 w-[352px] items-center rounded-2xl bg-white px-8 text-[#a5a5a5] shadow-[0_16px_30px_rgba(44,52,68,0.08)] sm:flex"><span className="sr-only">Search</span><input readOnly value="" placeholder="Search here" className="w-full bg-transparent outline-none placeholder:text-[#a5a5a5]" /><span className="text-2xl text-[#505050]" aria-hidden="true">⌕</span></label></div>
        </header>

        <div className="px-6 pb-9 pt-4 lg:px-6">
          <h1 className="mb-4 text-[24px] font-normal text-[#8b8b8b]">Expenses Comparison</h1>
          <section className="min-h-[258px] rounded-[10px] bg-white px-6 pb-5 pt-5 shadow-[0_18px_35px_rgba(33,43,54,0.08)]" aria-labelledby="monthly-comparison-title">
            <div className="flex flex-wrap items-center justify-between gap-4"><h2 id="monthly-comparison-title" className="font-semibold">Monthly Comparison <span aria-hidden="true" className="ml-2">⌄</span></h2><div className="flex gap-8 text-xs text-[#555]"><span className="flex items-center gap-2"><i className="h-2 w-4 rounded-sm bg-[#299d91]" />Current month</span><span className="flex items-center gap-2"><i className="h-2 w-4 rounded-sm bg-[#e7e7e7]" />Previous months</span></div></div>
            {isLoading ? <ChartSkeleton /> : error ? <div role="alert" className="flex h-[185px] items-center justify-center text-red-700">{error}</div> : summaryData.length === 0 ? <div className="flex h-[185px] items-center justify-center text-center text-[#666]">{emptyMessage}</div> : (
              <>
                <div className="h-[190px] w-full" aria-label="Monthly expense chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={summaryData} margin={{ top: 20, right: 8, left: 8, bottom: 0 }} accessibilityLayer>
                      <CartesianGrid vertical={false} stroke="#eeeeee" />
                      <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#9a9a9a', fontSize: 13 }} />
                      <YAxis axisLine={false} tickLine={false} width={65} tick={{ fill: '#9a9a9a', fontSize: 12 }} tickFormatter={(value: number) => `$${new Intl.NumberFormat('en-US', { notation: 'compact' }).format(value)}`} />
                      <Tooltip formatter={(value) => [typeof value === 'number' ? formatCurrency(value) : '—', 'Expense']} cursor={{ fill: 'rgba(41,157,145,0.06)' }} />
                      <Bar dataKey="totalExpense" radius={[5, 5, 0, 0]} maxBarSize={30}>{summaryData.map((item) => <Cell key={item.month} fill={item.month === currentMonth ? '#299d91' : '#e7e7e7'} />)}</Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <ul className="sr-only">{summaryData.map((item) => <li key={item.month}>{item.month}: {formatCurrency(item.totalExpense)}</li>)}</ul>
                {summaryData.length === 1 && summaryData[0]?.month === currentMonth && <p className="text-center text-xs text-[#777]">Record more transactions to compare monthly spending trends.</p>}
              </>
            )}
          </section>

          <section className="mt-7" aria-labelledby="breakdown-title">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 id="breakdown-title" className="text-[24px] font-normal text-[#8b8b8b]">Expenses Breakdown</h2>
              <label className="flex items-center gap-3 text-sm font-medium text-[#666]">Month<input type="month" value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)} disabled={isBreakdownLoading} className="rounded-lg border border-[#d8d8d8] bg-white px-3 py-2 text-[#555] outline-none focus:border-[#299d91] focus:ring-2 focus:ring-[#299d91]/30 disabled:cursor-wait disabled:opacity-60" /></label>
            </div>
            {isBreakdownLoading ? <BreakdownSkeleton /> : breakdownError ? <div role="alert" className="flex min-h-[240px] items-center justify-center rounded-[9px] bg-white px-6 text-center text-[#666] shadow-[0_18px_35px_rgba(33,43,54,0.08)]">{breakdownError}</div> : (
              <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3" aria-live="polite">
                {expensesData.map((card) => <article key={card.category} className="overflow-hidden rounded-[9px] bg-white shadow-[0_18px_35px_rgba(33,43,54,0.08)]"><div className="flex min-h-[78px] items-center bg-[#ededed] px-6"><span className="mr-4 flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-[#d5d5d5] text-xl" aria-hidden="true">{categoryIcon(card.category)}</span><div className="min-w-0"><h3 className="truncate text-[#666]">{card.category}</h3><p className="text-xl font-bold">{formatCurrency(card.Total)}</p></div><div className={`ml-auto pl-3 text-right font-semibold ${card.changePercent > 0 ? 'text-[#238b63]' : card.changePercent < 0 ? 'text-[#d92d20]' : 'text-[#666]'}`}>{Math.abs(card.changePercent).toLocaleString('en-US', { maximumFractionDigits: 2 })}% <span aria-hidden="true">{card.changePercent > 0 ? '↑' : card.changePercent < 0 ? '↓' : '–'}</span><p className="whitespace-nowrap text-xs font-normal text-[#888]">Compare to last month</p></div></div><div className="px-6">{card.subCategories.map((item, index) => <div key={`${item.item_description}-${item.date}-${index}`} className="flex items-center gap-4 border-b border-[#eee] py-5 last:border-b-0"><p className="min-w-0 flex-1 break-words font-semibold text-[#555]">{item.item_description}</p><div className="shrink-0 text-right"><p className="font-semibold text-[#555]">{formatCurrency(item.amount)}</p><p className="text-xs text-[#aaa]">{formatTransactionDate(item.date)}</p></div></div>)}</div></article>)}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function ChartSkeleton() {
  return <div role="status" aria-label="Loading monthly expenses" aria-busy="true" className="mt-5 flex h-[175px] animate-pulse items-end gap-6 border-b border-[#eee] px-10 motion-reduce:animate-none">{[45, 70, 35, 82, 60, 40, 68, 88, 60, 72, 30, 58].map((height, index) => <span key={`${height}-${index}`} className="flex-1 rounded-t bg-[#e5e7eb]" style={{ height: `${height}%` }} />)}</div>;
}

function BreakdownSkeleton() {
  return <div role="status" aria-label="Loading expense breakdown" aria-busy="true" className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <div key={index} className="h-[240px] animate-pulse overflow-hidden rounded-[9px] bg-white shadow-[0_18px_35px_rgba(33,43,54,0.08)] motion-reduce:animate-none"><div className="h-[78px] bg-[#e3e3e3]" /><div className="space-y-5 px-6 py-6"><div className="h-4 rounded bg-[#ededed]" /><div className="h-4 w-2/3 rounded bg-[#ededed]" /><div className="h-4 w-5/6 rounded bg-[#ededed]" /></div></div>)}</div>;
}
