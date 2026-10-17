import { Link } from 'react-router-dom';

export function NewBillPage() {
  return <section aria-labelledby="new-bill-title"><h1 id="new-bill-title" className="page-title">Set up a new invoice</h1><div className="bills-card bills-state"><p>Bill creation is not available in UC-012.</p><Link className="bills-action" to="/bills">Back to upcoming bills</Link></div></section>;
}
