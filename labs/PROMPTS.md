# Genie Code & Genie Prompt Playbook

Starter prompts for agentic development on Databricks, from the Publix workshop.
Copy, adapt, make them yours. The pattern: **describe → generate → review → deploy**.

This playbook is organized by **notebook** so you know when and how to use each prompt.
Swap the example names (`publix_agentic_workshop`, `gold_store_item_daily`, etc.) for your own.

---

## Hand-Out Notebooks (You Run These)

### Notebook 1 - Setup & Mock Data (`notebook_1_setup.py`)

This notebook is self-contained. Run it as-is - no Genie Code needed. It creates the catalog, schemas, and loads ~50 synthetic events into bronze tables.

---

### Notebook 2 - Kafka Producer (`notebook_2_kafka_producer.py`)

Optional notebook. If you have a Kafka broker (Docker, Redpanda, or production), run this to stream synthetic events from your laptop. Instructions are in the notebook; edit the `KAFKA_BOOTSTRAP_SERVERS` config at the top.

---

### Notebook 3 - Zerobus Ingest via Genie Code (`notebook_3_zerobus_genie_code.py`)

**This is the main Genie Code exercise for ingest.** Open Genie Code (Cmd/Ctrl + I) and run this prompt:

> **🧞 Prompt for Genie Code**
> ```
> Build a Python Zerobus publisher for Databricks. It should:
> - Use the Zerobus Ingest SDK (install: pip install databricks-zerobus-ingest-sdk)
> - Connect to the Zerobus endpoint: https://<workspace-id>.zerobus.eastus.azuredatabricks.net
> - Authenticate using a service principal (app_id and secret from Databricks secret scope publix_workshop)
> - Define two Zerobus streams:
>   1. publix_agentic_workshop.bronze.sales_events (6 realistic Publix products with prices)
>   2. publix_agentic_workshop.bronze.price_updates
> - For 60 seconds, publish synthetic events:
>   - 3-6 sales per second to sales_events (random store, product, quantity)
>   - Occasional price updates (10% chance per second)
> - Use fire-and-forget ingestion (ingest_record_nowait)
> - Flush and close streams cleanly at the end
> - Use environment variables for all credentials (DATABRICKS_WORKSPACE_URL, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET, ZEROBUS_SERVER_ENDPOINT, DURATION_SECONDS)
>
> Generate a production-ready script. Show me the plan and the code.
> ```

Save the generated code to `src/zerobus/publisher.py`. Compare your output to the reference solution in Notebook 3. Then deploy via DAB (see README runbook).

---

## Platform Layer Notebooks (Hands-On Exercises)

### Notebook 4 - Medallion Pipeline (SDP) (`notebook_4_sdp_medallion.py`)

**This is the main shared exercise.** Everyone builds it and lands in the same gold table.

**For the silver layer**, use this prompt:

> **🧞 Prompt for Genie Code**
> ```
> Build a streaming table called silver_sales in publix_agentic_workshop.medallion
> that reads from bronze.sales_events and:
> - Casts event_timestamp to TIMESTAMP
> - Casts quantity_sold to INT
> - Casts unit_price to DECIMAL(10, 2)
> - Casts total_amount to DECIMAL(12, 2)
> - Includes a constraint that drops rows where event_id or item_id is null
> - Uses liquid clustering on store_number and item_id
> Write it as a CREATE OR REFRESH STREAMING TABLE statement.
> ```

**For the gold layer**, use this prompt:

> **🧞 Prompt for Genie Code**
> ```
> Build a materialized view called gold_store_item_daily in the medallion schema
> that aggregates silver_sales to daily units sold, revenue, and line item counts
> grouped by store_number, item_id, item_name, item_category, and sales_date.
> Include SUM(quantity_sold) as units_sold, SUM(total_amount) as revenue,
> and COUNT(*) as line_items. Cast the date from event_ts. Write it as
> CREATE OR REFRESH MATERIALIZED VIEW.
> ```

Save both to `src/pipelines/transformations/` and deploy via DAB.

---

### Notebook 5 - Genie Spaces & Agents (`notebook_5_genie_spaces.py`)

**The goal:** Make `gold_store_item_daily` self-serve. Use Genie Code to draft the instructions and sample questions (or build the space in the Genie UI for a faster path).

**Write the instructions:**

> **🧞 Prompt for Genie Code**
> ```
> Write Genie space instructions for a "Store Performance" agent on `gold_store_item_daily`.
> State that revenue is daily and pre-aggregated by store, item, and date; define store_number,
> item_id, units_sold, revenue; and tell it to always group by the grain the user asks for.
> Keep it under 12 lines.
> ```

**Seed sample questions:**

> **🧞 Prompt for Genie Code**
> ```
> Give me three sample questions for this agent, from easy to hard: top items by revenue per
> store, day-over-day change in units for an item, and store ranking by revenue for a date range.
> For each, show the SQL you'd expect Genie to generate against `gold_store_item_daily`.
> ```

**Metric view (one example):**

> **🧞 Prompt for Genie Code**
> ```
> Draft a metric view over `gold_store_item_daily` with measures total_revenue (sum),
> avg_units_per_item (avg), and a store_rank by revenue, so Genie answers ranking questions
> consistently. Give me the DDL and how to point the Genie space at the metric view.
> ```

---

### Notebook 6 - Build & Ship an App (`notebook_6_build_ship_app.py`)

**Two paths:** App Builder (UI-driven, simpler) or CLI + manual dev (full control).

**App Builder (simpler):**

> Using App Builder in the workspace UI, create a snapshot app that queries the gold table:
> ```sql
> SELECT store_number, item_id, item_name, revenue, units_sold
> FROM publix_agentic_workshop.medallion.gold_store_item_daily
> ORDER BY revenue DESC
> ```
> Configure the UI, add store filter, and publish to a shareable URL.

**CLI + Manual Dev (more control, Genie Code can help draft the backend):**

> **🧞 Prompt for Genie Code**
> ```
> Set up a Node.js/React frontend + FastAPI backend locally. The backend queries
> `publix_agentic_workshop.medallion.gold_store_item_daily` via the Databricks SQL warehouse
> named `publix-workshop-wh`. Show me the app.yaml, the warehouse connection config, and the
> commands to deploy via `databricks bundle deploy`.
> ```

---

## Bonus: Encode Your Standards (optional but powerful)

If you plan to build many agents or pipelines, create an `AGENTS.md` (assistant instructions) once:

> **🧞 Prompt for Genie Code**
> ```
> Create an AGENTS.md (assistant instructions) for this repo. Capture how we name catalogs,
> schemas, and tables; how we tag data for governance; that pipelines must be Spark
> Declarative Pipelines in SQL, serverless, with liquid clustering; and that nothing deploys
> to prod outside our Asset Bundle + service-principal automation. Keep it concise.
> ```

From then on, Genie Code will follow your conventions in every generation.

---

## The Loop, Every Time

1. **Describe** - say what you want in plain English
2. **Generate** - Genie Code writes the code + shows a plan
3. **Review** - read the plan, compare to reference, keep a human in the loop
4. **Deploy** - ship it via `databricks bundle deploy` or Publish button

Genie Code is fast; your judgment is the guardrail.
