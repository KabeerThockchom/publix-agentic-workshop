export interface Summary {
  total_revenue: number;
  total_units: number;
  stores: number;
  items: number;
  start_date: string | null;
  end_date: string | null;
}

export interface StoreRow {
  store_number: string;
  revenue: number;
  units: number;
  items: number;
}

export interface ItemRow {
  item_id: string;
  item_name: string;
  item_category: string;
  revenue: number;
  units: number;
}

export interface TrendRow {
  sales_date: string;
  revenue: number;
  units: number;
}

export interface PriceRow {
  event_timestamp: string;
  item_id: string;
  item_name: string;
  old_price: number;
  new_price: number;
  pct_change: number;
  effective_date: string;
}

export interface ActionRow {
  action_id: number;
  store_number: string;
  item_id: string;
  action_type: string;
  amount: number | null;
  note: string | null;
  created_by: string;
  created_at: string;
}

export interface AppConfig {
  app: string;
  genie_configured: boolean;
  lakebase_configured: boolean;
  genie_space_id_set: boolean;
  genie_space_id?: string | null;
  genie_embed_url?: string | null;
  lakebase_reads?: boolean;
}

export interface GenieResult {
  configured: boolean;
  answer?: string | null;
  sql?: string | null;
  columns?: string[];
  rows?: unknown[][];
  error?: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  config: () => get<AppConfig>('/api/config'),
  summary: () => get<Summary>('/api/metrics/summary'),
  byStore: () => get<StoreRow[]>('/api/metrics/by-store'),
  byItem: () => get<ItemRow[]>('/api/metrics/by-item'),
  trend: () => get<TrendRow[]>('/api/metrics/trend'),
  prices: () => get<PriceRow[]>('/api/prices'),
  catalog: () => get<{ items: { item_id: string; item_name: string }[]; stores: string[] }>('/api/catalog'),
  actions: () => get<{ configured: boolean; actions: ActionRow[] }>('/api/actions'),
  createAction: (body: {
    store_number: string;
    item_id: string;
    action_type: string;
    amount: number | null;
    note: string | null;
  }) => post<{ configured: boolean; action: ActionRow }>('/api/actions', body),
  askGenie: (question: string) => post<GenieResult>('/api/genie/ask', { question }),
};

export function fmtMoney(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n);
}

export function fmtNum(n: number): string {
  return new Intl.NumberFormat('en-US').format(n);
}
