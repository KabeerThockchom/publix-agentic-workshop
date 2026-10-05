<p align="center"><img src="assets/publix.svg" height="40" alt="Publix"> &nbsp;×&nbsp; <img src="assets/databricks.svg" height="36" alt="Databricks"></p>

# Flagship: StoreSight IQ - Genie Code build playbook

We open the workshop with the finished **StoreSight IQ** app (real-time labor forecasting for Publix), then rebuild it **backward**, one layer at a time, with Genie Code. Each step below is a section: a short enablement beat, one **Genie Code prompt** (with the exact contract so it can't drift), and how to verify. Everything lands in your own schema `publix_labor_forecast.storesight_iq_<yourname>` - you set `<yourname>` once in Step 0 and Genie Code carries it through every step.

The build order and full data-flow map: see the decomposition plan. Bronze is raw; silver/gold cast + aggregate; the labor model is the hero.

---

## Step 0 - Claim your namespace (do this first)

**Enablement:** everyone builds in one shared workspace, so each participant works in their own schema and suffixes every workspace-global object (Model Serving endpoints, the Genie space, the app) with their name. Collisions - two people registering `labor_optimizer` or deploying `store-labor-planner` - break the room otherwise. Set the token once; Genie Code applies it to every later step.

> **🧞 Genie Code**
> ```
> For this entire StoreSight IQ build, my namespace token is <yourname> (lowercase, no spaces, e.g. sai).
> Use it everywhere, without me repeating it:
> - every table, view, model, and pipeline goes in catalog publix_labor_forecast, schema storesight_iq_<yourname>
> - Model Serving endpoints are named storesight-<model>-<yourname>
> - the Genie space is named "Publix Store Analytics - <yourname>"
> - the app is named "store-labor-planner-<yourname>"
> Confirm my schema name back to me, then apply this convention to every step that follows.
> ```
> **Verify:** Genie Code echoes `storesight_iq_<yourname>` and the suffixed endpoint/space/app names.
> *(Prefer zero typing? Instead tell Genie Code to derive the token from `SELECT current_user()` - the part before `@`, lowercased, dots to underscores.)*

---

## Step 1 - Unity Catalog foundation

**Enablement:** governed data starts with a catalog + schema + typed tables.

> **🧞 Genie Code**
> ```
> Create a Unity Catalog schema `storesight_iq_<yourname>` in catalog `publix_labor_forecast`, then
> these tables (USING DELTA), with realistic Publix grocery data:
> - stores(store_id INT, name STRING, address STRING, city STRING, state STRING, lat DOUBLE,
>   lng DOUBLE, region STRING, sqft INT, open_date DATE)  -- 24 real Publix stores (FL/Southeast)
> - menu_items(item_id INT, name STRING, category STRING, price DOUBLE)  -- Pub Sub, Rotisserie
>   Chicken, Chicken Tender Sub, Publix Bakery Bread, GreenWise Milk, Boar's Head Ham, Strawberries, Deli Platter
> - pos_transactions(txn_id STRING, store_id INT, ts TIMESTAMP, item_id INT, quantity INT,
>   total DOUBLE, channel STRING, payment_method STRING)  -- 120 days history, grocery hourly curve
> - employees(employee_id INT, store_id INT, name STRING, role STRING, hourly_rate DOUBLE, employment_type STRING)
> - labor_schedule(store_id INT, date DATE, hour INT, scheduled_staff INT, role STRING)
> - ingredients(ingredient_id INT, name STRING, category STRING, unit STRING, par_level INT, cost_per_unit DOUBLE)
> - inventory_levels(store_id INT, ingredient_id INT, date DATE, qty_on_hand INT, par_level INT, days_supply DOUBLE)
> Keep timestamps as TIMESTAMP, ids as INT, prices as DOUBLE. Show the DDL, then run it.
> ```
> **Verify:** Catalog Explorer shows the schema + 8 tables with data.

---

## Step 2 - Real-time ingest with Zerobus

**Enablement:** no Kafka cluster - Zerobus is a serverless push API. A Python producer streams live POS + curbside events straight into a bronze Delta table over gRPC, authenticated as a service principal.

> **🧞 Genie Code**
> ```
> Build a Python Zerobus publisher (databricks-zerobus-ingest-sdk) that streams synthetic Publix
> POS events into `publix_labor_forecast.storesight_iq_<yourname>.pos_events_bronze`.
> Table (raw): event_id STRING, store_id INT, event_timestamp STRING, item_id INT, item_name STRING,
>   category STRING, channel STRING, quantity INT, unit_price DOUBLE, total DOUBLE,
>   payment_method STRING, ingestion_time STRING. Enable Change Data Feed.
> Publisher: auth via service principal (client id + secret from env), 3-6 events/sec across 24
> stores and 8 products, channel mix in_store 78% / curbside 15% / delivery 7%, fire-and-forget
> (ingest_record_nowait), flush + close cleanly. Env vars for all credentials + DURATION_SECONDS.
> ```
> **Prereq:** grant the publisher SP `USE CATALOG` + `USE SCHEMA` + `SELECT, MODIFY` on the schema.
> **Run (laptop):** `DURATION_SECONDS=30 python producer/pos_publisher.py`
> **Verify:** `SELECT count(*), max(ingestion_time) FROM ...pos_events_bronze` climbs, seconds-fresh.
> *(Reference producer: `src/zerobus/pos_publisher.py`.)*

---

## Step 3 - Pipeline: silver + gold (SDP + metric views)

**Enablement:** raw isn't trustworthy yet. Declare the transform + quality rules; Databricks builds the DAG serverless and tracks lineage. Define KPIs once as metric views so the app and Genie agree.

> **🧞 Genie Code**
> ```
> Over `publix_labor_forecast.storesight_iq_<yourname>`, create:
> - SILVER streaming table `silver_pos` from STREAM(pos_events_bronze): cast event_timestamp->TIMESTAMP
>   (as event_ts), keep item_id INT, total DOUBLE; EXPECT event_id AND store_id NOT NULL ON VIOLATION
>   DROP ROW; CLUSTER BY (store_id, item_id).
> - GOLD materialized views:
>   * mv_daily_sales: by store_id, sales_date -> transactions, units, revenue
>   * mv_store_overview: per store -> sales_today/wtd/mtd/ytd, labor_cost_pct, rank
>   * mv_hourly_demand: by store_id, hour_of_day, day_of_week -> transactions (feeds the labor model)
> - A metric view `labor_metrics` (YAML, version 1.0): measures total_recommended, total_scheduled,
>   avg_labor_gap, forecast_txn_per_hour; dimensions store_id, hour, sales_date. Query with MEASURE().
> Show the SQL, then deploy as a serverless pipeline + the metric view.
> ```
> **Verify:** the DAG goes green; `SELECT store_id, MEASURE(total_recommended) FROM labor_metrics GROUP BY store_id`.

---

## Step 4 - The ML models (labor is the hero)

**Enablement:** four models on the same governed data. The **labor optimizer** predicts how many associates each store-hour needs; demand/inventory/prep round out ops. Train, register to Unity Catalog, serve.

> **🧞 Genie Code (labor optimizer - the hero)**
> ```
> Train a labor-optimization model on mv_hourly_demand + labor_schedule: a multi-class classifier
> predicting recommended staff (2-8) per store-hour from features [store_id, day_of_week, hour_of_day,
> is_weekend, recent transaction lags]. Use gradient boosting; log with MLflow; register to Unity
> Catalog as `publix_labor_forecast.storesight_iq_<yourname>.labor_optimizer`; deploy a Model Serving
> endpoint `storesight-labor-optimizer-<yourname>`. Report within-±1 accuracy. Handle class imbalance with balanced weights.
> ```
> Repeat the pattern for **demand-forecast**, **inventory-predictor**, **prep-scheduler** (each: train ->
> register to `storesight_iq_<yourname>` -> serve `storesight-<model>-<yourname>`).
> **Verify:** `databricks serving-endpoints list` shows all 4 READY.

---

## Step 5 - Genie space (ask labor questions in English)

**Enablement:** a manager asks in plain English, grounded on the governed gold + metric views - no SQL.

> **🧞 (Genie UI or API)** Create a Genie space "Publix Store Analytics - <yourname>" on `mv_store_overview`,
> `mv_daily_sales`, `mv_hourly_demand`, `labor_metrics`. Instructions: labor_gap>0 = understaffed;
> recommended is the ML forecast, scheduled is the plan; group by the grain asked. Sample questions:
> "Which stores are understaffed at 5pm on Fridays?", "Labor cost % of revenue by store", "How many
> deli associates does store 3 need Saturday lunch?".
> **Verify:** ask "Which store had the highest sales YTD?" -> real answer + SQL.

---

## Step 6 - Lakebase (serving + write-back)

**Enablement:** the app writes manager actions (orders, prep/staffing adjustments) to a Postgres OLTP store with sub-second reads, right next to the lakehouse.

> **🧞 Genie Code**
> ```
> Set up Lakebase for the app: create tables `inventory_orders(store_id, ingredient_id, ingredient_name,
> suggested_quantity, estimated_cost, urgency, PRIMARY KEY(store_id, ingredient_id))` and
> `prep_items(store_id, item, planned_batches, ...)`. Grant the app service principal USAGE + CREATE on
> schema public and SELECT/INSERT/UPDATE/DELETE on the tables. Show the SQL + the grant statements.
> ```
> **Verify:** app `/api/state/debug` lists the tables; a POST to `/api/state/inventory-orders/<id>` persists.

---

## Step 7 - Build + ship the app (Genie App Builder)

**Enablement:** describe the app in plain English; Genie App Builder generates it, embeds the Genie space, and deploys a Serverless Micro App - data-aware, no wiring.

> **🧞 Genie App Builder** (Apps -> Build -> select App Space -> "store-labor-planner-<yourname>")
> ```
> Build a real-time labor dashboard for a Publix store manager using mv_store_overview,
> mv_hourly_demand, labor_metrics and the "Publix Store Analytics - <yourname>" Genie space. Publix green #3E902D.
> - Store selector filtering the page.
> - KPI cards: forecast transactions/hour, recommended vs scheduled associates, labor gap (red if understaffed).
> - Hourly chart: scheduled vs ML-optimal staffing across the day.
> - Table of stores ranked by labor gap (most understaffed first).
> - Right-hand "Ask about staffing" panel wired to the Genie space (answer + SQL).
> - Let the manager adjust scheduled associates and save (write-back to Lakebase).
> ```
> **Verify:** live preview renders KPIs + chart + Ask panel; Deploy -> Serverless Micro App URL.
> *(Full-control alternative: the FastAPI+React reference in the StoreSight accelerator deployed via `wire_app.py`.)*

---

## The loop, every step
Describe -> Generate -> **Review** -> Run. The agent is fast; your review is the guardrail.
