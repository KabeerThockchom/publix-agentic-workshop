import { FormEvent, useEffect, useState } from 'react';
import { api, GenieResult } from '../lib/api';
import { Card } from './Card';

type Mode = 'ask' | 'embed';

export default function AskGenie() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('ask');
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GenieResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .config()
      .then((c) => {
        setConfigured(c.genie_configured);
        setEmbedUrl(c.genie_embed_url ?? null);
      })
      .catch(() => setConfigured(false));
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

      {configured && embedUrl && (
        <div className="mb-4 inline-flex rounded-lg border border-black/10 p-0.5 text-xs">
          <button
            onClick={() => setMode('ask')}
            className={`rounded-md px-3 py-1 font-medium transition ${
              mode === 'ask' ? 'bg-publix-green text-white' : 'text-navy/60 hover:text-navy'
            }`}
          >
            Ask Genie (API)
          </button>
          <button
            onClick={() => setMode('embed')}
            className={`rounded-md px-3 py-1 font-medium transition ${
              mode === 'embed' ? 'bg-publix-green text-white' : 'text-navy/60 hover:text-navy'
            }`}
          >
            Embed (iframe)
          </button>
        </div>
      )}

      {configured && mode === 'embed' && embedUrl && (
        <div>
          <div className="overflow-hidden rounded-lg border border-black/10">
            <iframe
              title="Genie space"
              src={embedUrl}
              width="100%"
              height="600"
              frameBorder="0"
              allow="clipboard-write"
              className="w-full bg-white"
            />
          </div>
          <p className="mt-2 text-xs text-navy/50">
            If this stays blank, Databricks blocks framing (X-Frame-Options / CSP). Use{' '}
            <button className="underline" onClick={() => setMode('ask')}>
              Ask Genie (API)
            </button>{' '}
            above, or{' '}
            <a className="underline" href={embedUrl} target="_blank" rel="noreferrer">
              open the Genie space in a new tab
            </a>
            .
          </p>
        </div>
      )}

      {configured && mode === 'ask' && (
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
