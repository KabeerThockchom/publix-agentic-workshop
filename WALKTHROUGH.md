# Zero-to-Hero Live Walkthrough


# Zero-to-Hero Live Walkthrough (UI + Genie Code)

How we run it live, on screen.
You drive everything in the browser - Genie Code writes the code, the Databricks UI shows it working.
The **only** thing on your laptop is the Zerobus publisher Python file.
No Databricks CLI in front of the audience.

Each step is the same shape:
- **Where** - the UI surface you're on.
- **Say** - the one line of talk track.
- **Do** - what you click.
- **Prompt** - what you paste into Genie Code (verbatim, ready to go).
- **Verify** - what proves it worked, **in the UI** (not a terminal).

The pattern the audience should feel every time: **Describe -> Genie Code generates -> you Review -> Run.**
The agent is fast; your review is the guardrail. Say that out loud on step 1 and don't stop saying it.

Workspace: `https://adb-<workspace-id>.<n>.azuredatabricks.net`.
Catalog/Schema: everyone shares this workspace and the shared `publix_technology` catalog, so **each person builds in their own schema** - `agentic_ai_training_<yourname>` (all layers in one schema). Kabeer demos with `agentic_ai_training_<yourname>`. Throughout this sheet, wherever a prompt says `publix_agentic_workshop`, read it as your own `publix_technology.agentic_ai_training_<yourname>` (lowercase, no spaces).
The already-built reference (Genie space, pipeline, apps) still exists - a live run rebuilds fresh copies, so IDs will differ from 72.16/72.18. That's fine; verify by the UI, not by ID.

---

## Pre-flight (do this before anyone's watching)

Browser:
- Logged into the workspace, warehouse running (SQL Warehouses -> your Serverless WH -> Start).
- Genie Code enabled (Settings -> Previews). See Previews to Enable (Publix) for the full list.

Laptop (the one local piece):
- Repo cloned, `.venv` built.
- Publisher env exported in the terminal you'll use (endpoint, workspace URL, SP client id/secret, `DURATION_SECONDS`).
  The exact export block is step 2 of Test & Validation Runbook - run it once, off-screen, so the live run is just one clean command.

---

## Instructor prep - empty workspace (done ahead of the session, not a live step)

The room opens on a **clean** workspace and builds from scratch starting at Step 1.
The clean slate is done ahead of time, not on-screen - participants never run a "drop everything."
Before the session, clean up old participant schemas from `publix_technology` (e.g., drop `agentic_ai_training_*` schemas), the `publix-medallion` pipeline, the `publix-zerobus-publisher` job, the Store Pulse app, and any Genie spaces from previous runs.
Kept: the Build Studio app (the take-home), the **Zerobus service principal** `publix-zerobus-publisher` (app id `<zerobus-sp-app-id>`), and the `publix_workshop` secret scope.

**The SP is one-time admin prep** (repo `SETUP_SERVICE_PRINCIPAL.md`): the publisher runs from the laptop as this SP, so participants only need their workspace login. But its **grants live inside the catalog** - dropping the catalog dropped them, so the SP is re-granted as the last beat of Step 1 (below). Skip that and the publisher 401s.

---

## Setup - Clone the repo (up front, before Step 1)

**Where:** Workspace -> Repos / Git folders, and your laptop terminal.
**Say:** "Everything we build lives in a repo. I clone it into the workspace - that's where Genie Code writes code and where the reference notebooks live - and once onto my laptop, just for the one thing that runs locally."
**Do:**
- Workspace -> **Repos / Git folders** -> **Add Git folder** -> paste `https://github.com/KabeerThockchom/publix-agentic-workshop`. This gives you the notebooks (the answer key), `PROMPTS.md` (every prompt, ready to paste), the SDP source, and the app reference.
- On your laptop: `git clone https://github.com/KabeerThockchom/publix-agentic-workshop` - only needed for the Zerobus publisher in step 2.

**Verify:** The Git folder shows `labs/`, `src/`, `app/`, `PROMPTS.md`.
**Note:** Genie Code writes *into* this folder - it doesn't replace it. If a live generation drifts, open the matching `notebook_N` and catch up. Prompts are in `labs/PROMPTS.md`.

---

## Setup - Local Python environment with uv (for the publisher)

**Where:** Your laptop terminal, inside the locally cloned repo.
**Say:** "The one thing we run off Databricks is the event publisher. We give it a clean, isolated Python environment with uv - fast, reproducible, no global installs. Watch, it's four commands."

**Do (step by step, on screen):**

1. **Install uv** (once - skip if `uv --version` already works):
   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   Then restart the shell or `source ~/.zshrc`, and confirm: `uv --version`.

2. **Create the virtual environment** (Python 3.11, matches Databricks LTS), from the repo root:
   ```
   cd publix-agentic-workshop
   uv venv --python 3.11
   source .venv/bin/activate
   ```
   Your prompt now shows `(publix-agentic-workshop)`. uv created `.venv/` - an isolated interpreter just for this project.

3. **Install the one dependency** the publisher needs:
   ```
   uv pip install -r requirements.txt
   ```
   That's just `databricks-zerobus-ingest-sdk`. Confirm the import works:
   ```
   python -c "import zerobus; print('zerobus SDK ready')"
   ```

4. **Set the four environment variables** the publisher reads (no secrets in code). In the **same** terminal:
   ```
   # workspace values (swap the workspace id/region for a participant's own)
   export ZEROBUS_SERVER_ENDPOINT="https://<workspace-id>.zerobus.<region>.azuredatabricks.net"
   export DATABRICKS_WORKSPACE_URL="https://adb-<workspace-id>.<n>.azuredatabricks.net"
   export WORKSHOP_SCHEMA="agentic_ai_training_<yourname>"   # your schema from Step 1 - the publisher writes here

   # service-principal creds - pulled from the secret scope so nothing is typed on screen
   export DATABRICKS_CLIENT_ID=$(databricks secrets get-secret publix_workshop zerobus_client_id --profile publix-workshop -o json | python3 -c "import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)['value']).decode())")
   export DATABRICKS_CLIENT_SECRET=$(databricks secrets get-secret publix_workshop zerobus_client_secret --profile publix-workshop -o json | python3 -c "import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)['value']).decode())")
   ```
   The SP needs INSERT on the bronze tables. (Participants set their own workspace id/region + SP.)

**Verify:**
   ```
   python -c "import os; print('all set:', all(os.environ.get(k) for k in ['ZEROBUS_SERVER_ENDPOINT','DATABRICKS_WORKSPACE_URL','DATABRICKS_CLIENT_ID','DATABRICKS_CLIENT_SECRET']))"
   ```
   Prints `all set: True`. You're ready to run the publisher in Step 2 - **in this same terminal** (the venv + env vars live here).

**Note:** run the credential `export`s off-screen or scroll past them - they resolve to a secret. Everything above lives in one terminal session; if you open a new tab, re-activate (`source .venv/bin/activate`) and re-export.

---

## Step 1 - Build the Unity Catalog foundation (Genie Code)

**Where:** Genie Code.
**Say:** "Before any data, we need a place to land it. I describe it in plain English, Genie Code writes the SQL, we review, we run. That review is the whole game. And since we all share this workspace, each of you builds in your **own** catalog - put your name in it."
**Do:** Open Genie Code, paste the prompt (swap `<yourname>` for your name), read the DDL it generates out loud, then Run. Tell participants to do the same with their name.
**Prompt:**
> Create the Unity Catalog foundation for a Publix real-time sales workshop.
> IMPORTANT: These are raw Kafka envelopes - do NOT flatten them (silver will explode and decode later).
> - Shared Catalog: `publix_technology`
> - Per-participant Schema: `agentic_ai_training_<yourname>`
> - Tables in your schema (USING DELTA, enable Change Data Feed on all):
> - Table `pos_sales_raw`: Kafka envelope structure
>   with nested value.Basket.BasketItems array (Gtin, Sku, Name, FamilyGroup, Quantity, UnitPrice, TotalPrice)
> - Bronze table `bronze.price_updates_raw` (USING DELTA, enable Change Data Feed): Kafka envelope with
>   base64-encoded data fields (Event_Timestamp, Effective_Date, Selling_Price, Deal_Price)
> - Create a Volume `bronze.kafka_landing` to stage JSON files for Auto Loader
> Show me the DDL, then run it.

**Why keep nested + base64:** Auto Loader lands raw JSON from Kafka topics exactly as-is. Silver is where we explode nested arrays and decode base64 fields. This preserves the full fidelity of the source systems (POSA and TPR) - if the source changes, we see it.

**Verify:** Catalog Explorer -> `publix_technology` -> `agentic_ai_training_<yourname>` -> you see `pos_sales_raw` and `price_updates_raw` tables and the `kafka_landing` Volume (all in the same schema). Point at the Change Data Feed property on the tables.

**Then grant the publisher SP (do this now, or Step 2 will 401):** the Zerobus publisher writes as the shared `publix-zerobus-publisher` service principal. You **own** the catalog you just made, so you grant that SP write on your own bronze schema (the SP app id is public - share it with the room). Paste into SQL Editor (or ask Genie Code to run it), with your catalog name:
```
GRANT USE CATALOG ON CATALOG publix_technology TO `<zerobus-sp-app-id>`;
GRANT USE SCHEMA  ON SCHEMA  publix_technology.agentic_ai_training_<yourname> TO `<zerobus-sp-app-id>`;
GRANT INSERT ON TABLE publix_technology.agentic_ai_training_<yourname>.pos_sales_raw TO `<zerobus-sp-app-id>`;
GRANT INSERT ON TABLE publix_technology.agentic_ai_training_<yourname>.price_updates_raw TO `<zerobus-sp-app-id>`;
```
`MODIFY` = write. Everyone grants the **same** SP on their **own** catalog (no admin rights, no per-person SP needed). Same grant is baked into `notebook_1` Part 4. **Say:** "Streaming ingest runs as a service identity, not as me - so I give that identity permission to write to my catalog, once."

---

## Step 2 - Zerobus real-time ingest (the one local run)

**Where:** Your laptop terminal, with Catalog Explorer open beside it to watch.
**Say:** "No Kafka cluster to stand up. Zerobus is a serverless push API - this Python file on my laptop streams events straight into the bronze Delta table over gRPC, authenticated as a service principal. Genie Code wrote this file too."
**Do (optional, show the generation):** In Genie Code, paste the prompt below so they see the publisher was AI-written. Then switch to your terminal and run the file.
**Prompt (optional):**
> Build a Python Zerobus publisher for Databricks. It should:
> - Use the Zerobus Ingest SDK (databricks-zerobus-ingest-sdk)
> - Connect to the workspace Zerobus endpoint, auth via service principal (client id + secret from env)
> - Define two streams: `publix_technology.agentic_ai_training_<yourname>.pos_sales_raw` (POSA Kafka envelope with nested Basket)
>   and `bronze.price_updates_raw` (TPR Kafka envelope with base64-encoded fields)
> - For 60s publish synthetic events: 3-6 POSA sales/sec (nested Basket with 1-8 items per store),
>   occasional TPR price updates (base64-encode Selling_Price and Effective_Date)
> - Fire-and-forget (`ingest_record_nowait`), flush + close cleanly

**Run (laptop, the only command you type live - in the terminal from the uv Setup, venv active + env vars set):**
`WORKSHOP_SCHEMA=agentic_ai_training_<yourname> DURATION_SECONDS=30 python src/zerobus/publisher.py`
It prints `[OK] Published N sales events.` (If you opened a fresh terminal: `source .venv/bin/activate` and re-export first.)

**Verify (in the UI):** Catalog Explorer -> `publix_technology` -> `agentic_ai_training_<yourname>` -> `pos_sales_raw` -> **Sample Data** tab, refresh -> rows are landing (check value.Basket.StoreNumber and value.Basket.BasketItems array). For a number on screen, open **SQL Editor** and run `SELECT count(*), COUNT(DISTINCT value.Basket.StoreNumber) as stores FROM publix_technology.agentic_ai_training_<yourname>.pos_sales_raw` before and after - the count jumps, stores match (8 distinct values).

**If it 401s (`invalid_authorization_details`):** you skipped the SP grant in Step 1, or the catalog was recreated after the grant. Run the three GRANTs from Step 1, then re-run the publisher.

**If it errors `Record decoder/encoder error ... expected a string`:** your bronze table types drifted from what the publisher sends (Genie Code typed `offset` as STRING or the Kafka `timestamp` as TIMESTAMP instead of BIGINT). This is why Step 1 pins the exact raw types. Recreate the two bronze tables with the Step 1 types, then re-run. Bronze is raw; silver casts.

---

## Step 3 - Medallion pipeline with SDP (Genie Code + Pipelines UI)

**Where:** Genie Code to generate, then Lakeflow Pipelines UI to run.
**Say:** "Raw data isn't trustworthy yet. Spark Declarative Pipelines let us declare the transform and the quality rules - Databricks builds the DAG, runs it serverless, tracks lineage end to end. We describe silver and gold; Genie Code writes the SQL."
**Do:** Paste the prompt, review the two SQL transforms. Then Workflows -> Pipelines (Lakeflow) -> Create pipeline -> Serverless -> point it at the generated SQL -> Start. (Or let Genie Code scaffold the pipeline and just hit Start in the UI.)
**Prompt:**
> Create a Spark Declarative Pipeline in SQL over `publix_technology.agentic_ai_training_<yourname>`:
> - SILVER `medallion.silver_pos_sales`: streaming table reading STREAM(bronze.pos_sales_raw); explodes value.Basket.BasketItems to one row per line item; extracts store_number, transaction_id, start_time, item_sku, item_gtin, item_name, item_family, quantity, unit_price, total_price; EXPECT (transaction_id IS NOT NULL AND item_sku IS NOT NULL) ON VIOLATION DROP ROW; CLUSTER BY (store_number, item_sku).
> - SILVER `medallion.silver_tpr_prices`: streaming table reading STREAM(bronze.price_updates_raw); base64-decodes Event_Timestamp, Effective_Date, Term_Date, Selling_Price, Deal_Price; extracts event_id, item_code, store_number, price_type, event_timestamp, selling_price, deal_price, effective_date; EXPECT (event_id IS NOT NULL AND item_code IS NOT NULL) ON VIOLATION DROP ROW; CLUSTER BY (store_number, item_code).
> - GOLD `medallion.gold_store_item_daily`: materialized view aggregating silver_pos_sales by store_number, item_sku, item_gtin, item_name, item_family, sales_date (CAST(start_time AS DATE)) -> COUNT(DISTINCT transaction_id) as num_transactions, SUM(quantity) as units_sold, SUM(total_price) as revenue, COUNT(*) as line_item_count, MIN/MAX/AVG(unit_price). (Price lives in silver_tpr_prices; weave it in at analysis time.)
> Give me all three SQL files and set it up as a serverless pipeline I can start.

**Verify (in the UI):** The Pipelines page draws the DAG bronze -> silver_pos_sales / silver_tpr_prices -> gold and turns each node green. Serverless cold start is ~3-5 min - narrate the lineage and quality-rule (dropped rows) counts while it runs. Then Catalog Explorer -> `medallion.silver_pos_sales` shows exploded line items; `gold_store_item_daily` is populated with daily aggregates by store/item/date.

---

## Step 4 - Govern the KPI with a metric view (Genie Code + SQL Editor)

**Where:** Genie Code to generate, SQL Editor to run and prove.
**Say:** "A number should mean the same thing in a dashboard and to an AI. A metric view defines revenue and units once, in Unity Catalog, so everything downstream agrees. You query it with MEASURE()."
**Do:** Paste the prompt, review the YAML, run the CREATE in SQL Editor, then run the MEASURE() query.
**Prompt:**
> Create a Unity Catalog metric view `medallion.store_performance_metric_view` on `gold_store_item_daily`:
> - measures: total_revenue = SUM(revenue), total_units = SUM(units_sold), avg_units_per_item = AVG(units_sold)
> - dimensions: store_number, item_sku, sales_date
> Use the YAML metric-view syntax (version 1.0, source in the YAML, no trailing SELECT). Give me the CREATE statement to run in the SQL editor, then a MEASURE() query to test it.

**Verify (in the UI):** SQL Editor result grid for
`SELECT store_number, MEASURE(total_revenue) AS rev FROM publix_technology.agentic_ai_training_<yourname>.store_performance_metric_view GROUP BY store_number ORDER BY rev DESC` -
stores ranked by revenue, top store ~104. No raw SUM anywhere - the governed measure did it.

---

## Step 5 - Ask in English: the Genie space (Genie UI)

**Where:** Genie (left nav).
**Say:** "Now a business user asks a plain-English question and gets an answer grounded in the governed data - no SQL, no BI ticket."
**Do:** Genie -> New space -> add `medallion.gold_store_item_daily` and the metric view -> give it a title and a couple of sample questions/instructions -> Save. Then ask a question in the space.
**Verify (in the UI):** In the Genie space, ask "Show me revenue by store, sorted highest to lowest." You get a natural-language answer, the generated SQL (expand it), and a result table - 8 stores, top 104. Ask one follow-up ("which item drove that?") to show it holds context.

---

## Step 6 - Build the app (Genie App Builder, no code)

**Where:** Apps home page -> Build tab.
**Say:** "Now we put all of it in front of a store manager - and we build the app by describing it, no code. Genie App Builder already knows our tables, our Unity Catalog semantics, and our Genie space, so there's nothing to wire up."
**Prereq (admin, before the room):** enable the **Governed agentic app-building** preview; create an **App Space** with the SQL warehouse + gold table + the Store Performance Genie space (as a Genie Agent resource) added; grant builders **CAN CREATE APP**. If the preview isn't on, skip to the reference app below.
**Do:** Apps home -> **Build** -> select the App Space -> name it "Store Pulse" -> paste the prompt.
**Prompt (from `labs/PROMPTS.md`, Notebook 6, Path A):**
> Build a store operations dashboard for a Publix store manager, using the gold table `publix_technology.agentic_ai_training_<yourname>.gold_store_item_daily` and the "Store Performance" Genie space in this App Space.
> - A store selector (store_number) at the top that filters the whole page.
> - KPI cards: total revenue, total units sold, and number of items sold, for the selected store.
> - A ranked horizontal bar chart of the top 10 items by revenue for the selected store.
> - A sortable table of items showing item_name, units_sold, and revenue.
> - A right-hand panel "Ask about this store" where the manager types a plain-English question and the Store Performance Genie space answers, showing the result and the SQL it ran.
> Keep it clean, fast, and readable.

**Do (iterate live):** Sign in to the preview, then add follow-ups so they see it change in the side pane: "Add a daily revenue trend line chart for the selected store." Then **Deploy** - it runs as a Serverless Micro App on a shareable URL.
**Verify (in the UI):** the live preview renders KPIs + chart + the Ask panel; a question in the panel returns a Genie answer. After Deploy, the app opens on its own URL.

**Then show the polished reference (art of the possible):** open Store Pulse - `https://publix-store-pulse-<workspace-id>.<n>.azure.databricksapps.com`
- **`/architecture`** - the live diagram: Zerobus -> SDP -> metric views -> Lakebase / Genie -> App, dot animating left to right. Your one-slide recap of the morning.
- Point out the extras a full build adds: sub-second reads off Lakebase, a refund/what-if write-back. "Genie App Builder got us a working app in minutes; with the FastAPI+React path in `app/` you get this."

**Say (the decompose):** "Everything behind that app is exactly the steps we just did - ingest, pipeline, governed metric, Genie, app. Describe, review, deploy, all the way up."

---

## The loop, say it every step

Describe -> Generate -> **Review** -> Run.
The agent is fast. Your review is the guardrail.
That single sentence is the point of the whole workshop - repeat it at every step.

---

Talk-track prose + the "why it matters" per step: Live Run Sheet & Talk Track.
Behind-the-scenes proof (CLI verification I already ran): Test & Validation Runbook.
Previews Publix must turn on first: Previews to Enable (Publix).
