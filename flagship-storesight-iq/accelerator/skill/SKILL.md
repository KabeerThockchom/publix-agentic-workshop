---
name: storesight-qsr-accelerator
description: >-
  Adapt the StoreSight IQ QSR demo (a Databricks App: UC + Model Serving +
  Lakebase + embedded Genie) to a NEW quick-service-restaurant customer. Runs a
  guided interview to fill the two config files, applies them with the
  generator, builds, and walks the human through the workspace-only steps and
  the DAB deploy. Trigger when a Databricks SA/SE wants to spin up a branded
  StoreSight IQ demo for a customer, "adapt/reskin StoreSight IQ", or build a
  QSR store-operations demo from this repo.
---

# StoreSight IQ — QSR Solution Accelerator (guided build)

Your job: take a fellow SA from "I want a StoreSight IQ demo for <customer>" to a
deployed, branded, working app — **fast** (target: an afternoon). You interview
them for the inputs, fill the configs, run the generator, build, and guide the
workspace steps. Never make them hand-edit code.

**Read these first** (they are the contract — do not duplicate their content):
`accelerator/customer_config.example.yaml`, `accelerator/domain.example.yaml`,
`accelerator/README.md`, `accelerator/WORKSPACE_STEPS.md`, `accelerator/BUILD_PLAN.md`.

## Ground rules
- **⛔ DEPLOYMENT ISOLATION — MANDATORY (this clobbered a prior customer TWICE).**
  Every customer is a fully net-new, isolated deployment. Two customers must NEVER
  share Terraform state, or deploying the 2nd DELETES the 1st's schema/app/jobs
  (a `bundle deploy` reconcile). Isolation hangs on ONE key — the customer's
  `short_code`. `generate.py` derives from it BOTH the unique `bundle.name`
  (`storesight-iq-<short_code>` → the REMOTE state root `…/.bundle/${bundle.name}`)
  AND the unique DAB **target** (`<short_code>`, not `dev` → the LOCAL state cache
  `.databricks/bundle/<target>/`, which persists across git branches in one working
  dir). BOTH matter. The structural bug is fixed, but these habits still matter:
  0. **The `short_code` MUST be globally UNIQUE per customer — never reuse a slug.**
     It is the single isolation key: two customers with the same `short_code` get
     the same bundle name AND target AND state, so the 2nd deploy overwrites the
     1st — and NO working-dir trick saves you (the remote state root collides too).
     `validate_naming` checks the slug's FORMAT, **not** its uniqueness — that's on
     you. Before choosing one, confirm no existing branch/deploy already uses it.
  1. **Run `generate.py` for THIS customer FIRST, then confirm `databricks.yml` was
     rewritten to it** — `bundle: name: storesight-iq-<short_code>` and the default
     target `<short_code>`. NEVER deploy a `databricks.yml` still carrying a prior
     customer's names (the classic slip: you swapped in new configs but forgot to
     regenerate, so the file — and the deploy — still points at the last customer).
  2. **Deploy each customer from a SEPARATE working directory** (fresh `git clone`
     or `git worktree`) so `.databricks/` (local state) is never shared. Belt-and-
     suspenders now that names are namespaced, but it makes step 3 unambiguous.
  3. **Before every `bundle deploy`, verify isolation:** run `databricks bundle
     summary` and read the local `.databricks/bundle/<target>/terraform/terraform.tfstate`
     — it must list ONLY this customer's resources (or be empty/new). If it names
     ANOTHER customer's schema/app, STOP — you are about to overwrite them.
  4. **NEVER `--auto-approve`** a deploy that reports deleting/recreating a schema,
     app, or job. That "data may be lost" prompt is the last safety net; a delete
     of a resource you didn't expect = STOP and investigate.
  5. Confirm afterward via `system.access.audit` (filter `databricks-tf-provider`)
     that no other customer's schema/app was deleted.
- **🌿 ALWAYS WORK ON A CUSTOMER BRANCH OFF `main` — never build or deploy on `main`.**
  Most people clone `main`, so the branch is what keeps `main` the clean, neutral
  template and gives each customer an isolated line of work (it complements — does
  not replace — the separate-working-dir habit above). The branch name is the
  **customer name, lowercased, special characters stripped, `snake_case` if
  multi-word** — e.g. "Mama's" → `mamas`, "Delta Subs" → `delta_subs` (note this
  differs from `short_code`, which has no underscores: `deltasubs`). **Infer it right
  after the identity round, then CONFIRM it with the SA at the end of the interview**
  (let them override), and create it off a fresh `main` BEFORE you generate anything
  (Step 1c). Every generated file + the force-committed configs land on this branch.
- **One source of truth.** Brand/naming/deploy → `customer_config.yaml`;
  product taxonomy → `domain.yaml`. Everything else is generated. Never edit
  `config/`, `app.yaml`, `frontend/src`, `databricks.yml`, or notebooks by hand
  to change customer values — change the configs and re-run the generator.
- **⚠️ PRESERVE THE CUSTOMER'S INPUTS — force-commit the two configs on the
  customer branch.** `accelerator/customer_config.yaml` + `domain.yaml` are
  gitignored (so they never pollute the neutral asset), which means on a customer
  branch they live ONLY in the working tree — a branch switch or `git clean` and
  they're gone. They ARE the customer (recovering them otherwise means digging
  through session transcripts). So on the per-customer branch, commit them
  explicitly: `git add -f accelerator/customer_config.yaml accelerator/domain.yaml`.
  Same for the customer's logo files under `accelerator/assets/`.
- **No committed secrets.** Ticketmaster (optional) goes in a Databricks secret.
- **Assess every component, every dimension.** Go file-by-file across the full
  stack (frontend components, api/, services/, notebooks/) and ask of each: does
  anything here encode the *customer or their domain* — name, color, logo, emoji,
  icon, product/menu/ingredient name, store, hours? If yes, it must be
  config-driven. `accelerator/audit.py` enforces this (Step 2b) — never skip it.
- **Test at each step** (frontend build, `bundle validate`, `/api/health`).
- **Automation vs human:** you do essentially everything. `bundle deploy` +
  `bundle run` build the data/ML/serving/genie/streaming; then
  `accelerator/wire_app.py` wires the app end-to-end (UC grants, the Lakebase
  Postgres grant, attaching endpoints/secret/Lakebase, `GENIE_SPACE_ID`, warming,
  embedding, deploy). The only genuinely human parts (`WORKSPACE_STEPS.md` §1) are
  one-time prerequisites — the catalog, SQL warehouse, Lakebase instance, and CLI
  profile must exist, the customer logo must be supplied, and the optional
  Ticketmaster secret created. The external-embedding toggle is automated too, but
  needs workspace-admin; if the caller isn't an admin, that one step is a manual
  fallback. Surface these clearly and wait for the human only where required.
- **📣 Narrate every step (clear, not verbose).** This is a guided experience — the
  SA should always know where they are and what's next. State the current step and
  what's coming in one short line as you go (e.g. "Step 1 of 5 · Identity & brand —
  next I'll web-search your logos", or "Deploy done → running the setup job next").
  Announce the phase transitions explicitly — interview → **confirmation gate** →
  generate + build → deploy → run setup → wire → verify — and after each command
  say what finished and what's next. Keep it to a line or two; never a wall of text.

---

## Step 1 — Interview (gather the inputs)

Interview the SA to **gather** the inputs — hold them in the conversation. Do NOT
write the config files yet: you copy the templates and fill in the gathered values
in **Step 2, only after the Step 1d confirmation gate**. Prefer QSR-typical defaults
and confirm rather than asking open-ended — keep it quick. (Logo image files are the
one thing you DO save during the interview — into `accelerator/assets/` — so you can
show/confirm them; the config *paths* to them are still written in Step 2.) The
templates you'll fill in Step 2:

```bash
# (run in Step 2, after the green light)
cp accelerator/customer_config.example.yaml accelerator/customer_config.yaml
cp accelerator/domain.example.yaml accelerator/domain.yaml
```

> **RESTORING / reusing a saved config?** If you're adapting from an existing
> `customer_config.yaml`/`domain.yaml` (a restore, or a copy of a prior customer)
> rather than a fresh interview, the interview is skipped — so you WON'T naturally
> hit the optional-integration prompts. Explicitly re-confirm them anyway before
> deploying: the **Ticketmaster** real-events key (a blank `ticketmaster_secret`
> means synthetic events — ask if they want real ones) and the **logos**. Don't
> silently accept whatever the saved config happened to contain.

**FIRST, determine: is this a REAL company or fictitious?** Ask (or infer from
the name, then confirm). This changes how you source stores and the logo:
- **Real** → do a quick **web search** for their real store locations and logo.
- **Fictitious** → prompt the SA for the inputs and synthesize (coords, logo).

Ask in grouped rounds (use AskUserQuestion where it helps):

**A. Identity & brand** → `customer_config.yaml: customer, brand`
- Customer name + a lowercase `short_code` (namespaces every resource).
- **🔤 Strip special characters when deriving ANY parameterized name.** QSR names
  are full of apostrophes, dashes, ampersands, periods and exclamation points
  ("Mama's", "Fresh-Mart", "Burger & Fry Co.", "O'Malley's", "Chef Lin's").
  The DISPLAY name (`customer.name`) keeps them verbatim (it's escaped for the UI),
  but the `short_code` and everything derived from it — schema, `resource_prefix`,
  endpoint / Lakebase / app / bundle names, DAB target, and notebook widget params
  — MUST be clean tokens with every special char removed:
  - `short_code`: lowercase, letters+digits only, no separators/spaces (e.g.
    "Fresh-Mart" → `freshmart`, "Mama's Hot Chicken" → `mamashotchicken`, "O'Malley's"
    → `omalleys`). `generate.py`'s `validate_naming()` HARD-FAILS on any
    stray char — produce a clean slug up front rather than tripping it.
  - **Working branch name** (inferred here, confirmed in Step 1c): lowercase,
    special chars stripped, `snake_case` if multi-word (e.g. "Mama's Hot Chicken" →
    `mamas_hot_chicken`, "Delta Subs" → `delta_subs`).
- Brand colors: primary + secondary (hex, with dark/light variants — offer to
  derive dark/light from the base if they only have one). Tagline.
- **🖼️ Logos — REQUIRED, gathered + confirmed DURING the interview (a hard gate).**
  You need two: a **main/full logo** (wordmark) and a **smaller icon/mark**
  (square-ish, for the nav avatar + favicon). For a **real company, ALWAYS
  web-search and pull the assets down yourself first** — do not default to asking:
  1. **Main logo:** search for the company's current official logo, preferring a
     **PNG or SVG with a transparent background**, high-res and up to date. If the
     best you find has a solid/opaque background, **remove the background** (flood-
     fill from the corners / color-key the matte, keep only the largest connected
     mark) while **preserving image quality** — no halos, no clipped glyphs. Save to
     `accelerator/assets/` and point `brand.logo_path` at it.
  2. **Smaller mark:** prefer an obvious *simpler* version of their modern logo
     (icon / monogram / emblem). If there's no confident simpler mark, instead make
     a **simple favicon of the thing they sell** (a sub roll for a sandwich shop, a
     burger for a burger chain, a doughnut for a doughnut shop, a coffee cup for a
     café), **branded in the company's colors** and matching the app's clean style.
     Save and point `brand.logo_circle_path` at it (SVG or PNG both work; the
     generator copies them and keeps the extension).
  - Both must look on-brand for the customer AND consistent with the app. Show the
    SA what you found/produced and confirm it before proceeding.
  - **Only if a thorough web search turns up nothing usable** do you explicitly ask
    the SA to paste a logo (or two) into the chat. Either way, **both assets must be
    in `accelerator/assets/` and confirmed before you edit the config or deploy** —
    this is a required interview gate, restated at the Step 1d confirmation.
  - **Fictitious company** → generate a neutral placeholder that picks up the brand
    colors (offer to draft a simple branded wordmark / product favicon).

**B. Databricks target** → `customer_config.yaml: databricks, lakebase, model_serving, app`
- CLI **profile** (run `databricks auth profiles` to list), workspace host + id.
- **📁 Catalog — ALWAYS ASK, immediately after the profile. Never assume one** —
  workspaces have many catalogs and guessing lands the demo in the wrong place.
  List them (`databricks catalogs list -p <profile>`) and have the SA pick the
  catalog to use; it must ALREADY EXIST (the accelerator does not run `CREATE
  CATALOG`). Then **state the `schema` you'll create inside it** (default
  `storesight_iq_<short_code>`) and **confirm it** with the SA before continuing.
- SQL warehouse id (must already exist; serverless is fine) and `resource_prefix`
  (defaults to `storesight-<short_code>`).
- Endpoint / Lakebase / app names default from `resource_prefix` — accept unless
  they need to match existing names.
- **External APIs — always ask, don't skip:**
  - **Weather** uses Open-Meteo (free, **no key**) — nothing to collect; just tell
    them it's included.
  - **Ticketmaster** (optional) powers the "local events" demand signal on Forecast
    + Operations alerts. The events module is **never blank** — with no key the app
    auto-populates fresh synthetic events (same format), so a key is only for REAL
    events. **Explicitly offer it.** If the SA wants real events, **collect the key
    NOW, during the interview** — do NOT defer it to after the deploy:
    1. Go to **https://developer.ticketmaster.com/explore/** → click **"Get Your API
       Key"** and sign up (free).
    2. Verify email + log in; open **"My Apps"** → copy the **Consumer Key**.
    3. Ask the SA to paste that Consumer Key into the chat now, and hold onto it.
    You'll reference it as `external_apis.ticketmaster_secret:
    "storesight-<short_code>/ticketmaster_api_key"`; you create the actual secret in
    Step 2 (before `generate.py`), and the **Step 1d confirmation gate restates that
    the key was gathered and the exact scope/name it will be stored under**. If the
    SA declines, leave `ticketmaster_secret` blank — synthetic events keep it alive.

**C. Product taxonomy** → `domain.yaml` (this is the real domain modeling).
Every field below is the SA's to control; each has a sensible fallback so you can
propose a QSR-typical default and let them confirm rather than block.
- **🍽️ For a REAL customer, web-search their ACTUAL, current menu FIRST** — signature
  items, popular products, core ingredients + categories, and typical dayparts —
  and use those findings to drive EVERY domain field below. The goal: every page
  reads like the real brand. The live transaction feed (Operations), the ingredient
  list + categories (Inventory), the prep subtypes (Prep Scheduler), and the
  `menu_items` shown throughout should all be the customer's **real products**, so
  the synthetic data generated from them looks authentic. Prefer real, up-to-date
  menu names over generic placeholders; confirm/tweak with the SA rather than
  inventing. (Fictitious customer → synthesize a plausible menu and confirm.)
- The **prep/production vertical**: what gets produced ahead of demand?
  - `prep.page_title` (nav label, e.g. "Bread Bake"), `verb` (bake/fry/proof/
    grill/press…), `item_noun` + `item_noun_plural` (e.g. "bread batch"/"bread
    batches" — plural falls back to noun+"s"), `unit` (e.g. loaves), and
    **`prep.emoji`** — the glyph shown on the prep surface (🥖/🍗/🌮…; fallback 🍽️).
  - `subtypes` — each with a unique integer id, prep_time_min, freshness_hours,
    popularity (should sum to ~1.0).
  - If the customer has no prep-ahead story, set
    `features.prep_scheduler_enabled: false` and skip this vertical.
- **Ingredients** + their **categories** (`ingredient_categories`) — drives the
  inventory page + the ML category encoding. **Menu items** (`menu_items`) — the
  customer's product names shown in the live transaction feed (fallback: derive
  from subtype labels). **Supplier** label (`supplier_name`).
- **Operating hours** (`operating_hours` open/close) + **dayparts** (non-overlapping,
  factors sum ~1.0) + **rush window** (`rush_hours`) + **labor dayparts**
  (`labor_dayparts` breakfast/lunch/dinner hour ranges — fallback: standard QSR).
- **Sales channels** (`sales_channels` — the order-mix keys/labels/shares).
- **Store fleet**:
  - **Real company** → **web-search their actual store locations** and offer the
    SA **groupings by region** (e.g. "Bay Area (18), SoCal (30), PNW (12)") to
    pick from; use the real cities + geocodes for the chosen group.
  - **Fictitious / can't find locations** → ask **how many stores** and **which
    metro / region** (e.g. "25 across the SF Bay Area") — never assume — then
    synthesize that many stores with real, plausible city names + lat/lng in that
    region. (lat/lng power the 3D map, which auto-centers on the fleet.)
- **Data volume** (`data_generation`) — days_of_history + transactions_per_day_avg
  (fallbacks: 365 / 200). Ask only if they care about scale; defaults are fine.
- **Genie sample questions** (`genie_sample_questions` — NL starters). `genie.space_name`
  / `description` and `customer.product_name` default from the customer name /
  stay "StoreSight IQ" — confirm, don't belabor.

Keep taxonomy consistent: subtype popularity and daypart factors each ~1.0; the
rush window should sit inside the peak daypart; menu_items should read like the
customer's real products.

### Step 1c — Confirm the branch name, then create it (off `main`)

Before you generate anything, restate the branch name you inferred in round A and
give the SA the chance to change it:

> "I'll do this build on branch **`<branch>`** (off `main`) — that keeps `main`
> clean and this customer isolated. Want a different name?"

Then create it from a fresh `main` (most people cloned `main`, so pull first):

```bash
git checkout main && git pull origin main
git checkout -b <branch>      # customer name, lowercased, snake_case if multi-word (e.g. delta_subs)
```

Everything from here — generate, build, the force-committed configs, and the
deploy — happens on this branch. **Never** run the build or a `bundle deploy` on
`main`.

### Step 1d — Confirmation gate: read back EVERYTHING, get the green light

**This is the single review gate. Do NOT edit the config files, create the secret,
or deploy anything until the SA explicitly greenlights.** With the interview
complete AND the logos gathered (Round A), present ONE organized, holistic summary
of every decision — clear but not verbose — grouped so the SA can scan it, change
anything, then approve:

- **Customer & brand:** display name, `short_code`, branch, tagline, primary/
  secondary brand colors (+ dark/light), and the two logo assets (say what you
  found/produced for each, and that they're saved in `accelerator/assets/`).
- **Workspace & asset names:** CLI profile, workspace host/id, **catalog**,
  **schema**, SQL warehouse id, `resource_prefix`, and the derived endpoint /
  Lakebase / app / bundle names + DAB target.
- **Integrations:** weather (Open-Meteo, no key); Ticketmaster — whether real
  events are on and, if so, that the **key was gathered** and the exact **secret
  scope/name** it will live under (`storesight-<short_code>/ticketmaster_api_key`).
- **Domain / taxonomy:** the prep-ahead vertical (title/verb/emoji/subtypes),
  ingredients + categories, `menu_items`, hours/dayparts/channels, the store fleet
  (count + region), data volume, and Genie sample questions — noting these were
  drawn from the customer's real menu where applicable.

End with an explicit ask: "Want to change anything? Otherwise I'll set the configs,
create the Ticketmaster secret (if any), and kick off the deploy." Only on a clear
yes do you proceed to Step 2. If the SA changes something, update and re-confirm the
affected lines (no need to replay the whole summary).

---

## Step 2 — Generate + build (automated)

> Only after the Step 1d green light. Narrate the transition: "Approved — setting
> configs and starting the deploy now."

**Write the two config files now** from the inputs you gathered: copy the templates,
then fill `customer_config.yaml` (brand, `short_code`, catalog/schema,
`resource_prefix`, logo paths, `ticketmaster_secret`) and `domain.yaml` (the full
menu / prep / store model). Then force-commit them on the customer branch (they're
gitignored — see the Preserve-inputs ground rule): `git add -f
accelerator/customer_config.yaml accelerator/domain.yaml` plus the logo files.

**If the SA opted into real Ticketmaster events, create the secret FIRST** (from the
Consumer Key you gathered in Round B) so the config references a secret that already
exists and the deploy can attach it — no retroactive step after the pipeline runs:

```bash
databricks secrets create-scope storesight-<short_code> -p <profile>
databricks secrets put-secret  storesight-<short_code> ticketmaster_api_key \
  --string-value "<the Consumer Key the SA pasted>" -p <profile>
```
Then set `external_apis.ticketmaster_secret: "storesight-<short_code>/ticketmaster_api_key"`
in `customer_config.yaml` (leave blank if they declined). **Never commit the key** —
only the `scope/key` reference goes in the config; the secret lives in the workspace.

```bash
python accelerator/generate.py --config accelerator/customer_config.yaml \
                               --domain accelerator/domain.yaml
# review what changed, then build the frontend:
cd frontend && npm install && npm run build && cd ..
```

- `--dry-run` first if they want a preview. The generator is idempotent — safe to
  re-run after tweaking a config value.
- Confirm the build passes. If a chart/logo looks wrong, fix the *config*, not
  the code, and regenerate.

## Step 2b — Audit EVERY component for residue (required gate)

Adapting is **not** just name + colors. Every component must be assessed across
every customer-specific **dimension**: brand name/copy, colors/tokens,
logos/favicons, **domain vocabulary** (product/menu/ingredient names), **emojis**,
**icons**, hardcoded data (stores, menu, ingredients), API/endpoint names, and
hardcoded numbers (store count, hours). A name-only pass once shipped a prior
customer's menu hardcoded in the demo endpoints and pizza emojis in a sandwich app.

Run the scanner and resolve it before deploying:

```bash
python accelerator/audit.py
```

- **FAIL** (prior-customer names) → must be zero.
- **HIGH** (hardcoded product/menu/ingredient names) → fix each: the value must
  come from `domain.yaml`, not a literal in code.
- **REVIEW** (food emojis, domain icons, raw hex) → confirm each is config-driven
  (`brand.config.ts` / `domain.yaml`) or intentionally generic.

If the scanner flags something no config can express yet, extend the config +
generator rather than hardcoding — that's how the accelerator stays reusable.

## Step 3 — Validate the bundle

```bash
databricks bundle validate -p <profile>
```

Fix any schema errors before deploying. (Auth errors mean the profile/host is
off in `customer_config.yaml`.)

## Step 4 — Deploy, run setup, then wire the app (automated)

```bash
databricks bundle deploy -p <profile>
databricks bundle run   storesight_setup -p <profile>   # nb 01→07: data + 4 MVs + ML + genie + streaming
python accelerator/wire_app.py            # --dry-run first to preview every action
```

`wire_app.py` performs the entire post-deploy wire-up that used to be manual —
UC grants to the app SP, the Lakebase Postgres grant
(`SET ROLE pg_database_owner; GRANT … CREATE ON SCHEMA public` — skipping it
causes `permission denied for schema public` at startup), attaching the serving
endpoints + secret + Lakebase to the app, setting `GENIE_SPACE_ID`, warming
endpoints, enabling external embedding, and `apps start`/`deploy` + a health poll.
It is idempotent; run `--dry-run` to preview. See `WORKSPACE_STEPS.md` for the
raw steps it runs.

> ⚠️ Never `databricks bundle deploy` after `wire_app.py` — it reconciles the app
> to the resources in `databricks.yml` and wipes what the script attached. Re-run
> `wire_app.py` if you must redeploy the bundle.

The **only** step that may need a human: the external-embedding toggle requires
workspace-admin. If the caller isn't an admin, `wire_app.py` logs it and you hand
them the one-line CLI/console fallback from `WORKSPACE_STEPS.md` §E.

## Step 5 — Verify

```bash
curl -s https://<app-url>/api/health     # expect "healthy" (warehouse + Lakebase + genie)
```
(`wire_app.py` already polls this at the end.)

Open the app and sanity-check: Login → Operations (live data), Forecast/Labor/
Inventory/Prep (ML recs), Regional Map (fleet), Compare (embedded Genie).

---

## If something's off
- Wrong brand/name/taxonomy anywhere → change the config, re-run `generate.py`,
  rebuild. Never patch generated files.
- ML endpoint errors → re-check the job run (nb 02–05) reached READY; the feature
  contract is single-sourced from `config/domain.json`, so a mismatch means the
  domain config changed after training — re-run the setup job.
- Reference: `accelerator/README.md` (overview + automation/human split),
  `WORKSPACE_STEPS.md` (the manual steps), `BUILD_PLAN.md` (how it's built).
