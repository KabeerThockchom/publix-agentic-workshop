# Design Notes & Build Overview

How the accelerator is put together and *why* — for anyone maintaining or
extending it. (To USE it, start with `accelerator/README.md` + the guided
skill; this file is the rationale behind the structure.)

## Locked design decisions

1. **Delivery = both.** A cleaned-up template repo (manifest + single taxonomy
   source + generator script + **DAB** + `wire_app.py` + README) usable by a
   human *or* an agent, PLUS a guiding skill wrapped around it.
2. **Parameterize via manifest + single taxonomy source**, both filled through a
   guided field-by-field interview. Brand tokens are neutral (`brand-primary` /
   `brand-secondary` CSS vars) so a re-skin is one place — naming a token after
   the customer forces edits across ~15 files and must not recur.
3. **One source of truth for the domain.** The product taxonomy lives in
   `config/domain.json` (generated from `domain.yaml`) and is read at runtime by
   BOTH the backend and the training notebooks, so the ML feature contract can't
   drift. The generator projects naming/brand/config; it never bakes taxonomy
   into Python.
4. **5th vertical = configurable "prep / production scheduler" abstraction.**
   Generalizes any make-ahead concept (bake, fry, proof, press…) to any QSR prep
   step; toggleable via `features.prep_scheduler_enabled` (hides the nav item +
   route when false).

## What changes customer-to-customer

- **Tier 1 — mechanical (100% automated by the generator):** names/namespaces
  (`config/settings.py`, `app.yaml`, notebook widget defaults), brand colors
  (`index.css` tokens + `brand.config.ts`), logos/favicon, product-name string,
  Genie space name/description + starter questions.
- **Tier 2 — semantic domain (agent builds, a human confirms the model):** the
  prep vertical (subtypes + vocabulary), the ingredient taxonomy + category
  encoding, operating hours + dayparts, and the geocoded store fleet — all in
  `domain.yaml`, feeding the ML feature contract that notebooks 04 & 05 consume.
- **Tier 3 — workspace wiring (automated by `wire_app.py`):** UC grants to the
  app SP, the Lakebase Postgres grant, attaching serving endpoints + secret +
  Lakebase to the app, `GENIE_SPACE_ID`, endpoint warming, external embedding,
  and app start/deploy. The only genuinely human parts are one-time
  prerequisites (catalog, SQL warehouse, Lakebase instance, CLI profile, logo,
  optional Ticketmaster secret) — see `WORKSPACE_STEPS.md` §1.

The 6 non-prep surfaces (Operations, Forecast, Labor, Inventory, Map, Compare)
are generic QSR store-ops — only data/brand/naming change, not logic.

## Hazards designed out (durable lessons)

- **Brand-named design tokens** → neutral `brand-*` CSS-var tokens, re-skinned in
  one place.
- **ML feature-contract drift** between backend and notebooks → single
  `domain.json` source + generator projection (never two hand-synced copies).
- **Committed secrets** (e.g. a live Ticketmaster key in `app.yaml`) → placeholder
  + Databricks secret reference only; `audit.py` + the commit hook guard it.
- **Genie serialized-space JSON is strict**: `version: 2`, `data_sources.tables`
  sorted by identifier, `config.sample_questions[].id` = 32-hex, `instructions`
  is an object. Notebook 06 builds it programmatically.
- **Filename-aware renames**, not just text substitution (a training-notebook
  file once kept an old vertical's name in its filename).
- **Notebook 01 must NOT `CREATE CATALOG`** (the catalog pre-exists; `CREATE`
  fails when account default storage is off).
- **Date-fragile views**: KPI views anchor to `MAX(DATE(...))` in the data, not
  `CURRENT_DATE()`, so static synthetic data doesn't read as $0 / -100% a day
  after generation.
- **App speed + Genie grounding**: notebook 01 builds 4 materialized views
  (`mv_daily_sales`, `mv_employees`, `mv_inventory`, `mv_store_overview`) that the
  app and the Genie space read.
- **Generic internals, not just generic copy**: filenames, routes, and state keys
  use a neutral `prep` vocabulary (no food-specific naming baked into the code).
- **No dead config flags**: a documented option (e.g. `prep_scheduler_enabled`)
  must actually do something, or it erodes trust in the asset.

## How it's built

- **`accelerator/generate.py`** (PyYAML, build-time, idempotent, `--dry-run`):
  applies `customer_config.yaml` + `domain.yaml` → `config/domain.json`,
  `config/settings.py`, `app.yaml`, `index.css` brand vars, `brand.config.ts`
  (identity + prep vocab + `prepSchedulerEnabled`), the logos, `index.html`, both
  layout store arrays, the Inventory category tabs, the notebook widget defaults
  (naming + warehouse id + Genie space name/description), and the `databricks.yml`
  variables. Re-running with the same config is a no-op.
- **`databricks.yml`** (DAB): the UC schema resource, a `storesight_setup`
  multi-task job running notebooks 01→07 on serverless (passing widget params),
  and the app — which declares ONLY the SQL warehouse resource. The 4 serving
  endpoints + secret + Lakebase are attached after the job by `wire_app.py`
  (endpoints don't exist at first deploy, and `bundle deploy` would otherwise
  reconcile the app's resource set and wipe them). No `mode: development` (it
  would prefix a phantom schema); a fixed `root_path` keeps redeploys stable.
- **Notebooks 01→07**: data generation + streaming + the 4 MVs (01), train +
  serve the 4 models (02–05, `cloudpickle` serialization + endpoint-readiness
  polling), create the Genie space over the MVs (06), streaming job (07).
- **`accelerator/wire_app.py`**: the whole post-job workspace wiring, idempotent,
  `--dry-run`-able (see `WORKSPACE_STEPS.md`).
- **`accelerator/audit.py`**: a full-stack gate — residue (prior-customer names,
  hardcoded product/menu names, food emojis/icons/raw hex) + pipeline
  completeness (MVs exist, the view is date-robust, the Genie space is created,
  the backend reads the MV). Wired into the skill as a required step.
- **Config contract**: `customer_config.yaml` + `domain.yaml` are the only
  hand-filled files, and are gitignored — only the `*.example.yaml` templates and
  neutral placeholder logos are tracked.

## Verification approach

The neutral repo is a self-consistent generation from the example configs:
`generate.py --config …example.yaml --domain …example.yaml --dry-run` reports
zero changes. Before shipping a customer build: `npm run build`, `py_compile` the
Python, `audit.py` clean (0 FAIL / 0 HIGH / 0 PIPELINE-FAIL), and — on the target
workspace — `bundle validate` → deploy → run → `wire_app.py` → `/api/health`.
