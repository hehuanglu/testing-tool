import axios from 'axios';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchSavingsSummary, type MonthlySavings } from '../../api/savings';
import { useAuth } from '../../context/auth-context';

const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;
const noDataMessage = 'There is no transaction data for this year to calculate savings.';
const safeErrorMessage = 'Unable to load data. Please try again later.';

interface ChartRow {
  month: string;
  thisYear: number;
  lastYear: number;
}

function seriesMap(series: readonly MonthlySavings[]): ReadonlyMap<string, number> {
  return new Map(series.map((item) => [item.month, item.amount]));
}

function currency(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
}

function axisCurrency(value: number): string {
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000) return `${value < 0 ? '-' : ''}$${(absolute / 1_000_000).toFixed(1)}m`;
  if (absolute >= 1_000) return `${value < 0 ? '-' : ''}$${Math.round(absolute / 1_000)}k`;
  return `${value < 0 ? '-' : ''}$${absolute}`;
}

export function SavingsSummaryChart() {
  const currentYear = new Date().getFullYear();
  const years = useMemo(() => Array.from({ length: 5 }, (_, index) => currentYear - index), [currentYear]);
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [thisYear, setThisYear] = useState<MonthlySavings[]>([]);
  const [lastYear, setLastYear] = useState<MonthlySavings[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef(0);
  const { logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++activeRequest.current;
    setIsLoading(true);
    setError(null);
    setThisYear([]);
    setLastYear([]);
    void fetchSavingsSummary(selectedYear, controller.signal)
      .then((payload) => {
        if (activeRequest.current !== requestId) return;
        setThisYear(payload.thisYear);
        setLastYear(payload.lastYear);
      })
      .catch((failure: unknown) => {
        if (axios.isCancel(failure) || activeRequest.current !== requestId) return;
        if (axios.isAxiosError(failure) && failure.response?.status === 401) {
          logout();
          navigate('/login', { replace: true, state: { sessionMessage: 'Please log in again.' } });
          return;
        }
        setError(safeErrorMessage);
      })
      .finally(() => {
        if (activeRequest.current === requestId) setIsLoading(false);
      });
    return () => controller.abort();
  }, [logout, navigate, selectedYear]);

  const chartData = useMemo<ChartRow[]>(() => {
    const selected = seriesMap(thisYear);
    const previous = seriesMap(lastYear);
    return monthLabels.map((month, index) => {
      const key = String(index + 1).padStart(2, '0');
      return { month, thisYear: selected.get(key) ?? 0, lastYear: previous.get(key) ?? 0 };
    });
  }, [lastYear, thisYear]);
  const isEmpty = !isLoading && !error && thisYear.length === 0 && lastYear.length === 0;

  return (
    <section className="rounded-xl bg-white p-6 shadow-[0_14px_28px_rgba(33,43,54,0.08)]" aria-labelledby="saving-summary-heading">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <h2 id="saving-summary-heading" className="text-lg font-bold text-[#4b4b4b]">Saving Summary</h2>
        <label className="relative text-sm text-[#777]">
          <span className="sr-only">Select savings year</span>
          <select
            value={selectedYear}
            onChange={(event) => setSelectedYear(Number(event.target.value))}
            disabled={isLoading}
            className="appearance-none rounded bg-transparent py-2 pl-2 pr-7 outline-none focus:ring-2 focus:ring-[#299d91] disabled:cursor-wait"
          >
            {years.map((year) => <option key={year} value={year}>{year}</option>)}
          </select>
          <span aria-hidden="true" className="pointer-events-none absolute right-1 top-1/2 -translate-y-1/2">⌄</span>
        </label>
        <div className="ml-auto flex flex-wrap gap-5 text-sm text-[#777]" aria-label="Chart legend">
          <span><b className="text-[#299d91]">━</b> This Year</span>
          <span><b className="text-[#cfd2d5]">━</b> Same period last year</span>
        </div>
      </div>

      <div className="mt-5 h-[205px] min-w-0" aria-live="polite">
        {isLoading ? (
          <div className="flex h-full items-center justify-center" role="status"><span className="h-9 w-9 animate-spin rounded-full border-4 border-[#d9efec] border-t-[#299d91]"/><span className="sr-only">Loading savings summary</span></div>
        ) : error ? (
          <div className="flex h-full items-center justify-center px-4 text-center text-red-700" role="alert">{error}</div>
        ) : isEmpty ? (
          <div className="flex h-full items-center justify-center px-4 text-center text-[#777]">{noDataMessage}</div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, bottom: 0, left: 5 }} accessibilityLayer>
                <CartesianGrid stroke="#e8e9ea" vertical />
                <XAxis dataKey="month" tickLine={false} axisLine={{ stroke: '#dfe1e3' }} tick={{ fill: '#999', fontSize: 12 }} />
                <YAxis tickFormatter={axisCurrency} tickLine={false} axisLine={false} tick={{ fill: '#999', fontSize: 12 }} width={58} />
                <Tooltip formatter={(value) => currency(Number(Array.isArray(value) ? value[0] ?? 0 : value ?? 0))} contentStyle={{ border: '1px solid #e5e7e9', borderRadius: 8 }} />
                <Line type="monotone" dataKey="thisYear" name={`${selectedYear}`} stroke="#299d91" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                <Line type="monotone" dataKey="lastYear" name={`${selectedYear - 1}`} stroke="#cfd2d5" strokeWidth={2} strokeDasharray="5 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <table className="sr-only">
              <caption>Monthly net savings for {selectedYear} and {selectedYear - 1}</caption>
              <thead><tr><th>Month</th><th>{selectedYear}</th><th>{selectedYear - 1}</th></tr></thead>
              <tbody>{chartData.map((row) => <tr key={row.month}><th>{row.month}</th><td>{currency(row.thisYear)}</td><td>{currency(row.lastYear)}</td></tr>)}</tbody>
            </table>
          </>
        )}
      </div>
    </section>
  );
}
