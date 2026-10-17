import { useState } from 'react';
import type { Bill } from '../../api/bills';

function safeLogo(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

function ProviderLogo({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);
  const safe = safeLogo(url);
  // The frozen dataset supplies these exact reference provider marks as a raster asset.
  if (safe === 'https://cdn.figma.com/logo.png') return <span className="provider-logo provider-figma" role="img" aria-label="Figma logo" />;
  if (safe === 'https://cdn.adobe.com/logo.png') return <span className="provider-logo provider-adobe" role="img" aria-label="Adobe logo" />;
  if (!safe || failed) return <span className="provider-fallback" role="img" aria-label="Provider logo unavailable">Bill</span>;
  return <img className="provider-image" src={safe} alt="Bill provider logo" referrerPolicy="no-referrer" onError={() => setFailed(true)} />;
}

export function BillRow({ bill }: { bill: Bill }) {
  const due = new Date(`${bill.dueDate}T00:00:00Z`);
  const lastCharge = new Date(`${bill.lastChargeDate}T00:00:00Z`);
  const [title, ...details] = bill.itemDescription.split('\n');
  return (
    <div role="row" className="bill-grid bill-row">
      <div role="cell"><time className="due-tile" dateTime={bill.dueDate}>
        <span>{due.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })}</span>
        <strong>{due.getUTCDate()}</strong>
      </time></div>
      <div role="cell"><ProviderLogo key={bill.logoUrl} url={bill.logoUrl} /></div>
      <div role="cell" className="bill-description"><strong>{title}</strong>{details.length > 0 && <p>{details.join('\n')}</p>}</div>
      <div role="cell" className="last-charge"><time dateTime={bill.lastChargeDate}>{lastCharge.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).replace(/ (\d{4})$/, ', $1')}</time></div>
      <div role="cell" className="bill-amount"><strong>{new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 4 }).format(bill.Amount)}</strong>
        <button type="button" disabled title="Payment is not available in this read-only view" aria-label="Pay Now — payment unavailable in this view">Pay Now</button>
      </div>
    </div>
  );
}
