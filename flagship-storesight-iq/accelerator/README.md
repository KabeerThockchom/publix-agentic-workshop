# StoreSight IQ — QSR Solution Accelerator

Turn the **StoreSight IQ** Databricks App (a real-time QSR store-operations
demo — Unity Catalog + Model Serving + Lakebase + embedded Genie) into a demo
for **any** Quick-Service Restaurant customer, in an afternoon instead of a week.

Proven across multiple QSR customer deployments. This accelerator captures
everything that changed between those builds so the next account team doesn't
rediscover it.

> ⛔ **Isolation (read before deploying a 2nd customer).** Every customer is a
> net-new, isolated deployment. `generate.py` namespaces the DAB bundle **and**
> target from the customer's `short_code`, so their Terraform state never collides —
> **but** you must (1) give each customer a **globally unique `short_code`** (the
> uniqueness isn't auto-checked), (2) **re-run `generate.py`** so `databricks.yml`
> carries *this* customer before deploying, and (3) deploy each from a **separate
> working directory**, never `--auto-approve`-ing a deploy that reports deleting a
> schema/app. Skipping this is how a prior customer's deployment got overwritten.
> Full rule: `skill/SKILL.md` (ground rules) and `WORKSPACE_STEPS.md`.

---

## Two ways to drive it

1. **Guided (recommended):** run the accelerator skill. It interviews you
   field-by-field, writes `customer_config.yaml` + `domain.yaml`, applies them,
   deploys via the DAB, wires the app with `wire_app.py`, and verifies
   `/api/health`.
2. **By hand:** copy the two `*.example.yaml` files, fill them in, run
   `python accelerator/generate.py`, `databricks bundle deploy` +
   `bundle run storesight_setup`, then `python accelerator/wire_app.py`.

Either way the inputs are identical — the skill is a front-end over the same
manifest + generator + DAB.

---

## The two config files

| File | Holds | Who fills it |
|---|---|---|
| `customer_config.yaml` | Brand, names, colors, Databricks deploy targets | Anyone (mostly lookups) |
| `domain.yaml` | Product taxonomy, ingredients, stores, hours, dayparts | Needs **domain modeling** — a person confirms the QSR's real menu/ops |

`domain.yaml` is deliberately the single source of truth for the ML feature
contract, so the backend and the training notebooks can't drift apart (a
failure mode that cost time on an earlier build).

---

## What is automated vs. what needs a human

### 🤖 Fully automated by the generator / DAB
- All naming (catalog, schema, endpoints, Lakebase, app, Genie space)
- Brand re-skin (neutral `brand-primary` / `brand-secondary` tokens — one place)
- Copy / labels, the 5th-surface prep vocabulary
- Genie space JSON (valid: version 2, sorted tables, 32-hex sample-question ids)
- Synthetic data + the 4 materialized views + ML training (notebooks 01–07,
  wired as a DAB job)
- App build + `databricks bundle deploy` + health check

### 🤖 Fully automated by `wire_app.py` (the post-deploy wire-up)
Everything that used to be a manual UI step (see `WORKSPACE_STEPS.md` §3):
- UC grants to the app SP (`USE_CATALOG` / `USE_SCHEMA` / `SELECT`)
- The Lakebase Postgres grant (`SET ROLE pg_database_owner; GRANT … CREATE ON
  SCHEMA public`) — without it the app's `_ensure_tables()` fails with
  `permission denied for schema public`. *UC grant ≠ Postgres grant; two separate
  permission systems.*
- Attaching the 4 serving endpoints + secret + Lakebase to the app
- Setting `GENIE_SPACE_ID`, warming endpoints, and `apps start`/`deploy`
- Enabling external embedding (needs workspace-admin — the one possible fallback)

### 🤝 Automated build, human decides (the interview)
- The **domain model** in `domain.yaml`: product subtypes, ingredients +
  categories, operating hours + dayparts, and the store fleet (geocodes).
  The accelerator proposes QSR-typical defaults; a human confirms/edits.

### 👤 Human, once (prerequisites — `WORKSPACE_STEPS.md` §1)
1. Ensure the **UC catalog**, **SQL warehouse**, **Lakebase instance**, and **CLI
   profile** exist (the accelerator doesn't create catalogs or warehouses), and
   **pick the catalog** when the interview asks (it's never assumed).
2. **Logos** are web-sourced during the interview (transparent PNG/SVG, background
   removed if needed; a product-style favicon in brand colors for the small mark) —
   you only paste one in if a thorough search finds nothing.
3. *(Optional)* provide a **Ticketmaster Consumer Key** during the interview for real
   local-events data — the secret is created for you before deploy.
4. *(If not a workspace admin)* run the one-line external-embedding toggle
   `wire_app.py` would otherwise do for you.

---

## Directory

```
accelerator/
  customer_config.example.yaml   # brand + naming + deploy targets  (manifest)
  domain.example.yaml            # product taxonomy (single source of truth)
  generate.py                    # applies the configs to code/notebooks/DAB
  audit.py                       # full-stack residue scanner (run after generate,
                                 #   before deploy — FAIL/HIGH must be resolved)
  wire_app.py                    # automated post-deploy wire-up (grants, resources,
                                 #   genie env, embedding, app deploy — no UI)
  skill/SKILL.md                 # the guided-interview skill (Option A)
  WORKSPACE_STEPS.md             # prerequisites + the raw steps wire_app.py runs
  BUILD_PLAN.md                  # how this accelerator is being built
  assets/                        # customer logo/favicon files go here
```

See `BUILD_PLAN.md` for design decisions and the phased construction status.
