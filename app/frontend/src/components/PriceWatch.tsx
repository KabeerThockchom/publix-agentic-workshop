import { useEffect, useState } from 'react';
import { api, PriceRow } from '../lib/api';
import { Card } from './Card';

export default function PriceWatch() {
  const [rows, setRows] = useState<PriceRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.prices().then(setRows).catch((e) => setError(String(e)));
  }, []);

  return (
    <Card title="Price watch" subtitle="Recent item price changes (price_updates)" accent>
      {error && <p className="text-sm text-lava">Failed to load: {error}</p>}
      {!error && (
        <div className="max-h-[420px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white">
              <tr className="border-b border-black/10 text-left text-xs uppercase tracking-wide text-navy/50">
                <th className="pb-2 pr-3 font-medium">Item</th>
                <th className="pb-2 pr-3 text-right font-medium">Old</th>
                <th className="pb-2 pr-3 text-right font-medium">New</th>
                <th className="pb-2 text-right font-medium">Change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const up = r.pct_change >= 0;
                return (
                  <tr key={i} className="border-b border-black/5 last:border-0">
                    <td className="py-2 pr-3">
                      <div className="font-medium text-navy">{r.item_name}</div>
                      <div className="text-xs text-navy/40">{r.effective_date}</div>
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums text-navy/60">${r.old_price.toFixed(2)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums font-medium text-navy">${r.new_price.toFixed(2)}</td>
                    <td className="py-2 text-right">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${
                          up ? 'bg-lava/10 text-lava' : 'bg-publix-light text-publix-dark'
                        }`}
                      >
                        {up ? '▲' : '▼'} {Math.abs(r.pct_change).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && !error && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-sm text-navy/40">
                    No price changes yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
