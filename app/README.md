# Publix Store Pulse

Flagship "art of the possible" demo for the Publix agentic workshop - a Databricks App
(FastAPI + React) that reads the Publix lakehouse gold layer, writes real OLTP actions to
Lakebase, and answers natural-language questions via Genie.

**Live URL:** https://publix-store-pulse-<workspace-id>.17.azure.databricksapps.com
**Workspace (FEVM):** adb-<workspace-id>.17.azuredatabricks.net (profile `publix-workshop`)

## Features

1. **Store performance dashboard** - revenue + units by store/item, top stores, and a
   revenue trend, read live from `publix_agentic_workshop.medallion.gold_store_item_daily`
   via the SQL warehouse (`publix-workshop-wh`,
   `<warehouse-id>`) using SDK statement execution.
   *Note: Workshop participants should override the catalog in `app.yaml` to point at their own `publix_agentic_<yourname>` catalog.*
2. **Price watch** - recent item price changes from `publix_agentic_workshop.medallion.silver_tpr_prices` or the gold aggregates.
   *Note: Workshop participants should override the catalog to point at their own `publix_agentic_<yourname>` catalog.*
3. **Action panel** - submit refund / price_override / whatif -> INSERT into Lakebase
   `public.store_actions` (instance `<lakebase-instance>`, database `publix_app`); recent
   actions listed below (SELECT). This is the read-write OLTP piece.
4. **Ask Genie** - Q&A panel calling the Genie Conversations API. `GENIE_SPACE_ID` is a
   config placeholder in `app.yaml`; the panel degrades gracefully until the id is supplied.

## Architecture

```
frontend/ (React + Vite + Tailwind)  ->  built to frontend/dist/
      |
      v  (served by)
app.py (FastAPI)
  ├── server/warehouse.py   reads  -> SQL warehouse (statement execution)
  ├── server/lakebase.py    OLTP   -> psycopg2 to Lakebase Postgres (public.store_actions)
  ├── server/genie.py       Q&A    -> Genie Conversations REST API
  └── server/config.py      dual-mode auth (ambient SP in-app, CLI profile locally)
```

## Auth

Dual-mode (`server/config.py`): in a deployed app it uses the ambient service principal
(`WorkspaceClient()`); locally it uses the `publix-workshop` CLI profile. FMAPI base is
`{host}/serving-endpoints`; Sonnet 5 rejects `temperature` (omitted). The app SP
(`<app-service-principal-id>`) is granted CAN_USE on the warehouse, SELECT on the
`medallion`/`bronze` schemas, and CONNECT/CREATE + table/sequence privileges on Lakebase.

## Local dev

```bash
# backend
uv venv --python 3.12 .venv && uv pip install -r requirements.txt
DATABRICKS_CONFIG_PROFILE=publix-workshop .venv/bin/python app.py   # serves :8000

# frontend (proxies /api -> :8000)
cd frontend && npm install --registry=https://npm-proxy.cloud.databricks.com/ && npm run dev
```

> The corporate npm proxy lags npm on `browserslist`/`caniuse-lite`; `frontend/package.json`
> pins them via `overrides` to versions the proxy mirrors.

## Deploy

```bash
cd frontend && npm run build && cd ..
databricks sync . /Workspace/Users/<you>/publix-store-pulse --profile publix-workshop --full
databricks apps deploy publix-store-pulse \
  --source-code-path /Workspace/Users/<you>/publix-store-pulse --profile publix-workshop
```

The Lakebase `database` resource is attached via `databricks apps update` (see `app.yaml`
comments). After first deploy, grant the app SP on the `publix_app` database:

```sql
GRANT USAGE, CREATE ON SCHEMA public TO "<sp_client_id>";
GRANT ALL PRIVILEGES ON public.store_actions TO "<sp_client_id>";
GRANT USAGE, SELECT ON SEQUENCE public.store_actions_action_id_seq TO "<sp_client_id>";
```

## Configure Genie

When the Genie space id is available, set `GENIE_SPACE_ID` in `app.yaml`, re-sync, and
redeploy. The Ask Genie panel activates automatically.
