import { FormEvent, useEffect, useState } from 'react';
import { ActionRow, api } from '../lib/api';
import { Card } from './Card';

const ACTION_TYPES = [
  { value: 'refund', label: 'Refund' },
  { value: 'price_override', label: 'Price override' },
  { value: 'whatif', label: 'What-if' },
];

export default function ActionPanel() {
  const [configured, setConfigured] = useState(true);
  const [actions, setActions] = useState<ActionRow[]>([]);
  const [stores, setStores] = useState<string[]>([]);
  const [items, setItems] = useState<{ item_id: string; item_name: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [store, setStore] = useState('');
  const [item, setItem] = useState('');
  const [type, setType] = useState('refund');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');

  function refresh() {
    api
      .actions()
      .then((r) => {
        setConfigured(r.configured);
        setActions(r.actions);
      })
      .catch(() => setConfigured(false));
  }

  useEffect(() => {
    refresh();
    api
      .catalog()
      .then((c) => {
        setStores(c.stores);
        setItems(c.items);
        if (c.stores[0]) setStore(c.stores[0]);
        if (c.items[0]) setItem(c.items[0].item_id);
      })
      .catch(() => {});
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await api.createAction({
        store_number: store,
        item_id: item,
        action_type: type,
        amount: amount ? Number(amount) : null,
        note: note || null,
      });
      setMsg('Action recorded in Lakebase.');
      setAmount('');
      setNote('');
      refresh();
    } catch (err) {
      setMsg(`Failed: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  if (!configured) {
    return (
      <Card title="Action panel" subtitle="Lakebase OLTP writes">
        <p className="text-sm text-navy/60">
          Lakebase is not attached. Add the <code className="rounded bg-black/5 px-1">postgres</code> database
          resource to enable refunds, price overrides, and what-if actions.
        </p>
      </Card>
    );
  }

  const inputCls =
    'w-full rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-publix-green focus:ring-1 focus:ring-publix-green';

  return (
    <Card title="Action panel" subtitle="Write to Lakebase (public.store_actions)" accent>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-navy/60">Store</span>
            <select className={inputCls} value={store} onChange={(e) => setStore(e.target.value)}>
              {stores.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-navy/60">Item</span>
            <select className={inputCls} value={item} onChange={(e) => setItem(e.target.value)}>
              {items.map((it) => (
                <option key={it.item_id} value={it.item_id}>
                  {it.item_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-navy/60">Action</span>
            <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
              {ACTION_TYPES.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-navy/60">Amount ($)</span>
            <input
              className={inputCls}
              type="number"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
            />
          </label>
        </div>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-navy/60">Note</span>
          <input
            className={inputCls}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional context"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-publix-green py-2.5 text-sm font-semibold text-white transition hover:bg-publix-dark disabled:opacity-50"
        >
          {busy ? 'Submitting…' : 'Submit action'}
        </button>
        {msg && (
          <p className={`text-xs ${msg.startsWith('Failed') ? 'text-lava' : 'text-publix-dark'}`}>{msg}</p>
        )}
      </form>

      <div className="mt-5 border-t border-black/5 pt-4">
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-navy/50">Recent actions</div>
        <div className="max-h-56 space-y-2 overflow-y-auto">
          {actions.map((a) => (
            <div key={a.action_id} className="flex items-center justify-between rounded-lg bg-surface px-3 py-2 text-sm">
              <div>
                <span className="font-semibold text-navy">{a.action_type}</span>
                <span className="text-navy/50">
                  {' '}
                  · store {a.store_number} · item {a.item_id}
                </span>
                {a.note && <div className="text-xs text-navy/40">{a.note}</div>}
              </div>
              <div className="text-right">
                {a.amount != null && <div className="font-medium tabular-nums text-navy">${a.amount.toFixed(2)}</div>}
                <div className="text-xs text-navy/40">{new Date(a.created_at).toLocaleString()}</div>
              </div>
            </div>
          ))}
          {actions.length === 0 && <p className="text-sm text-navy/40">No actions yet.</p>}
        </div>
      </div>
    </Card>
  );
}
