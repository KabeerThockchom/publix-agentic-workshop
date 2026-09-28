# Genie Code Prompt Playbook

A starter set of Genie Code prompts for agentic development on Databricks, from the
Publix workshop. Copy, adapt, and make them yours. The point is not the exact wording -
it is the pattern: describe what you want, let Genie Code generate and plan, review, deploy.

Swap the example names (`publix_agentic_workshop`, `gold_store_item_daily`, etc.) for your
own catalog, schemas, and tables.

---

## 0. Encode your standards first

Genie Code follows your conventions if you give it context. Do this once and every
generation gets better.

> Create an AGENTS.md (assistant instructions) for this repo. Capture how we name catalogs,
> schemas, and tables; how we tag data for governance; that pipelines must be Spark
> Declarative Pipelines in SQL, serverless, with liquid clustering; and that nothing deploys
> to prod outside our Asset Bundle + service-principal automation. Keep it concise.

> Load our ETL framework as an Agent Skill so generated pipeline code uses it instead of a
> generic template. Point it at <path/to/framework> and summarize the conventions it enforces.

---

## 1. Explore your data

> Show me the tables in `publix_agentic_workshop.bronze`, and for `sales_events` give me the
> row count, the schema, and 5 sample rows.

> Profile `publix_agentic_workshop.medallion.gold_store_item_daily`: distinct stores and
> items, date range, and the top 10 items by revenue.

---

## 2. Real-time ingest (Zerobus)

> Explain how Zerobus ingest works and when I would use it instead of a Kafka connector or
> Auto Loader, in three bullets.

> Write a Python publisher that streams synthetic grocery sales events (store, item, quantity,
> unit price, timestamp) into `publix_agentic_workshop.bronze.sales_events` using the Zerobus
> ingest SDK. Read the service-principal client id and secret from the `publix_workshop` secret
> scope, use fire-and-forget ingestion, and run for 30 seconds.

> Add a second stream that emits item price-update events into `bronze.price_updates`.

---

## 3. Medallion pipeline (Spark Declarative Pipelines)

> Create a Spark Declarative Pipeline in SQL. Bronze is `bronze.sales_events` (populated by
> Zerobus). Build a silver streaming table that reads bronze as a stream, casts types, drops
> rows with a null event_id or item_id, and clusters by store and item. Then build a gold
> materialized view of daily units sold and revenue by store and item.

> Assemble these SQL files into a serverless pipeline and give me the Asset Bundle config to
> deploy it. Then show me how to run it and validate row counts at each layer.

> The silver table needs to handle late-arriving events. Add a quality expectation and explain
> what happens to rows that violate it.

---

## 4. Genie spaces - build, scope, and onboard (do it properly)

**Build**

> Draft the general instructions for a Genie space on
> `publix_agentic_workshop.medallion.gold_store_item_daily`. Explain the grocery domain: what
> a store, item, category, units_sold, and revenue mean, and the vocabulary a merchandising
> analyst would use.

**Scope**

> This gold table has store, item, category, date, units, revenue. Recommend what to include
> in the Genie space and what to leave out to keep answers accurate, and why. Should I add the
> silver table, or keep the space focused on gold?

**Onboard**

> Draft 8 certified example questions for this space, each with the correct SQL against
> `gold_store_item_daily` (top items by revenue, revenue by store, week-over-week trend,
> category mix, and a few more). These become the trusted examples the space learns from.

> Draft two metric definitions for this space as SQL expressions: total revenue, and average
> units per line item.

**Ontology**

> Explain Genie ontology in plain terms and how setting it up (certified metrics, relationships,
> synonyms) improves answer accuracy. Then propose the ontology entries for our store/item/sales
> domain.

---

## 5. Genie One

> Explain how Genie One routes a question across multiple Genie spaces, and what I need to do
> to add our store-sales space to it.

> Given these three spaces (store sales, inventory, pricing), write example cross-domain
> questions that Genie One should route correctly, and say which space each should hit.

---

## 6. Build and ship an app (Genie Code CLI)

> Scaffold a small Databricks App that shows top items by revenue and lets me filter by store,
> reading from `publix_agentic_workshop.medallion.gold_store_item_daily` through a SQL
> warehouse. Use FastAPI and React, not Streamlit.

> Wire the app to our SQL warehouse, add an app.yaml, and give me the commands to deploy it as
> a Databricks App via our Asset Bundle and service principal. Open a PR first - I want to
> review the plan before anything deploys.

---

## The loop, every time

Describe → Generate → **Review** (read the plan, open a PR, keep a human in the loop) → Deploy.
Genie Code is fast; your judgment is the guardrail.
