import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  api,
  fmtMoney,
  fmtNum,
  ItemRow,
  StoreRow,
  Summary,
  TrendRow,
} from '../lib/api';
import { Card } from './Card';

const GREEN = '#4c8c2b';
const NAVY = '#0B2026';

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-black/5 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-navy/50">{label}</div>
      <div className="mt-1 text-3xl font-bold text-navy">{value}</div>
      {sub && <div className="mt-1 text-xs text-navy/50">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [stores, setStores] = useState<StoreRow[]>([]);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [trend, setTrend] = useState<TrendRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.summary(), api.byStore(), api.byItem(), api.trend()])
      .then(([s, st, it, tr]) => {
        setSummary(s);
        setStores(st);
        setItems(it);
        setTrend(tr);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <Card title="Store performance">
        <p className="text-sm text-lava">Failed to load lakehouse data: {error}</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat
          label="Total revenue"
          value={summary ? fmtMoney(summary.total_revenue) : '—'}
          sub={summary ? `${summary.start_date} → ${summary.end_date}` : ''}
        />
        <Stat label="Units sold" value={summary ? fmtNum(summary.total_units) : '—'} />
        <Stat label="Stores" value={summary ? fmtNum(summary.stores) : '—'} />
        <Stat label="Items" value={summary ? fmtNum(summary.items) : '—'} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Revenue trend" subtitle="By sales date" accent>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trend} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="sales_date" tick={{ fontSize: 11 }} tickFormatter={(d) => d?.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => fmtMoney(v)} />
              <Line type="monotone" dataKey="revenue" stroke={GREEN} strokeWidth={3} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Top stores by revenue" accent>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stores.slice(0, 10)} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="store_number" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => fmtMoney(v)} />
              <Bar dataKey="revenue" radius={[6, 6, 0, 0]}>
                {stores.slice(0, 10).map((_, i) => (
                  <Cell key={i} fill={i === 0 ? GREEN : NAVY} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Revenue by item" subtitle={`${items.length} items`} accent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-black/10 text-left text-xs uppercase tracking-wide text-navy/50">
                <th className="pb-2 pr-4 font-medium">Item</th>
                <th className="pb-2 pr-4 font-medium">Category</th>
                <th className="pb-2 pr-4 text-right font-medium">Units</th>
                <th className="pb-2 text-right font-medium">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.item_id} className="border-b border-black/5 last:border-0">
                  <td className="py-2 pr-4 font-medium text-navy">{it.item_name}</td>
                  <td className="py-2 pr-4 text-navy/60">
                    <span className="rounded-full bg-publix-light px-2 py-0.5 text-xs text-publix-dark">
                      {it.item_category}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums text-navy/80">{fmtNum(it.units)}</td>
                  <td className="py-2 text-right font-semibold tabular-nums text-navy">{fmtMoney(it.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
