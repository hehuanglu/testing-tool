import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchUpcomingBills, type Bill } from '../api/bills';
import { BillRow } from '../components/bills/BillRow';

export function BillsPage() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [request, setRequest] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    async function load() {
      setIsLoading(true);
      setError(null);
      setBills([]);
      try {
        const rows = await fetchUpcomingBills(controller.signal);
        if (active) setBills(rows);
      } catch {
        if (active) {
          setBills([]);
          setError('Unable to load invoice list. Please try again.');
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; controller.abort(); };
  }, [request]);

  return (
    <section aria-labelledby="bills-title">
      <h1 id="bills-title" className="page-title">Upcoming Bills</h1>
      <div className="bills-card" aria-busy={isLoading}>
        {isLoading ? <div role="status" className="bills-state"><span className="sr-only">Loading upcoming bills</span><div className="bill-skeleton" /><div className="bill-skeleton" /></div> :
          error ? <div className="bills-state"><p role="alert">{error}</p><button className="bills-action" type="button" disabled={isLoading} onClick={() => { setIsLoading(true); setRequest((value) => value + 1); }}>Retry</button></div> :
          bills.length === 0 ? <div className="bills-state"><p>You don&apos;t have any bills due soon.</p><Link className="bills-action" to="/bills/new">Set up a new invoice</Link></div> :
          <div role="table" aria-label="Upcoming bills" className="bills-table">
            <div role="row" className="bill-grid bill-head">{['Due Date', 'Logo', 'Item Description', 'Last Charge', 'Amount'].map((heading) => <div role="columnheader" key={heading}>{heading}</div>)}</div>
            <div role="rowgroup">{bills.map((bill) => <BillRow key={bill.billId} bill={bill} />)}</div>
          </div>}
      </div>
    </section>
  );
}
