import { FormEvent, useEffect, useState } from 'react';
import { api, GenieResult } from '../lib/api';
import { Card } from './Card';

export default function AskGenie() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GenieResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.config().then((c) => setConfigured(c.genie_configured)).catch(() => setConfigured(false));
  }, []);

  async function ask(e: FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.askGenie(question);
      setResult(r);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const samples = [
    'What were total sales by store last week?',
    'Which item had the highest revenue?',
    'Show revenue trend by day',
  ];

  return (
    <Card title="Ask Genie" subtitle="Natural-language Q&A over the lakehouse" accent>
      {configured === false && (
        <div className="rounded-lg border border-dashed border-black/15 bg-surface p-4 text-sm text-navy/60">
          <div className="font-semibold text-navy">Genie not configured</div>
          Set <code className="rounded bg-black/10 px-1">GENIE_SPACE_ID</code> in <code className="rounded bg-black/10 px-1">app.yaml</code> once the Genie space is provisioned, then redeploy.
        </div>
      )}

      {configured && (
        <>
          <form onSubmit={ask} className="flex gap-2">
            <input
              className="flex-1 rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-publix-green focus:ring-1 focus:ring-publix-green"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about sales, stores, items…"
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-navy px-4 py-2 text-sm font-semibold text-white transition hover:bg-navy/90 disabled:opacity-50"
            >
              {busy ? 'Thinking…' : 'Ask'}
            </button>
          </form>
          <div className="mt-2 flex flex-wrap gap-2">
            {samples.map((s) => (
              <button
                key={s}
                onClick={() => setQuestion(s)}
                className="rounded-full border border-black/10 px-3 py-1 text-xs text-navy/60 transition hover:border-publix-green hover:text-publix-dark"
              >
                {s}
              </button>
            ))}
          </div>

          {error && <p className="mt-3 text-sm text-lava">{error}</p>}
          {result?.error && <p className="mt-3 text-sm text-lava">{result.error}</p>}

          {result?.answer && (
            <div className="mt-4 rounded-lg bg-surface p-4 text-sm text-navy">{result.answer}</div>
          )}
          {result?.sql && (
            <pre className="mt-3 overflow-x-auto rounded-lg bg-navy p-3 text-xs text-white/90">{result.sql}</pre>
          )}
          {result?.columns && result.columns.length > 0 && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-black/10 text-left text-navy/50">
                    {result.columns.map((c) => (
                      <th key={c} className="pb-1 pr-3 font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(result.rows || []).slice(0, 25).map((row, i) => (
                    <tr key={i} className="border-b border-black/5">
                      {(row as unknown[]).map((cell, j) => (
                        <td key={j} className="py-1 pr-3 tabular-nums text-navy/80">
                          {String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
