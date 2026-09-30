# Publix Agentic Workshop - Labs

Databricks Asset Bundle for the Publix agentic developer workshop.
Built and tested in a FEVM Azure Serverless workspace (`eastus`), profile `publix-workshop`.

**The spine: Spark Declarative Pipelines medallion.** Everyone runs Notebook 4 and lands in the same gold table.
Then we query it together (Notebook 5) and ship an app (Notebook 6).

Vault home: `Obsidian Vault/60-69 Projects/72 Publix Agentic Workshop/` (plan + runbook).

## Hand-Out Notebooks (Publix participants run these)

Three self-contained notebooks you run on your side:

1. **Notebook 1 - Setup & Mock Data** (`notebook_1_setup.py`)
   - Creates catalog `publix_agentic_workshop`, schemas `bronze` and `medallion`
   - Creates `bronze.sales_events` and `bronze.price_updates` tables (Change Data Feed enabled)
   - Generates and loads ~50 synthetic Publix sales events + ~5 price updates
   - **Duration:** ~5 min
   - **Outcome:** Ready-to-query bronze tables

2. **Notebook 2 - Kafka Producer** (`notebook_2_kafka_producer.py`)
   - Optional: Streams synthetic sales/price events from your laptop via Kafka
   - Includes setup instructions for Docker Kafka or local Redpanda
   - If Kafka is unavailable, Notebook 1's mock data is sufficient
   - **Duration:** ~2 min (if Kafka is ready)
   - **Outcome:** Real-time events flowing (if Kafka is available)

3. **Notebook 3 - Zerobus Ingest via Genie Code** (`notebook_3_zerobus_genie_code.py`)
   - Guided code generation: you describe, Genie Code builds the publisher
   - Deploys as a DAB job that pushes synthetic events into bronze tables
   - Our tested reference implementation is included for comparison
   - **Duration:** ~10 min
   - **Outcome:** Zerobus publisher running; bronze tables live with streaming data

## DAB-Managed Platform (we deploy and iterate)

Then the platform layers are deployed and managed via Databricks Asset Bundles:

4. **Notebook 4 - Medallion Pipeline (SDP)** (`notebook_4_sdp_medallion.py`)
   - Everyone builds silver + gold layers using Spark Declarative Pipelines
   - Shared exercise output: `publix_agentic_workshop.medallion.gold_store_item_daily`
   - **Duration:** ~30 min
   - **Outcome:** All participants' data in the same gold table

5. **Notebook 5 - Genie Spaces & Agents** (`notebook_5_genie_spaces.py`)
   - Create a Genie agent on the gold table for business users
   - Write instructions, seed sample questions, test Genie One routing
   - Metric views for consistent KPI definitions
   - **Duration:** ~20 min
   - **Outcome:** Self-serve query interface for the gold table

6. **Notebook 6 - Build & Ship an App** (`notebook_6_build_ship_app.py`)
   - App Builder (simple) or Databricks CLI + manual dev (full control)
   - Deploy a UI that queries `gold_store_item_daily` via a SQL warehouse
   - Ship via DAB
   - **Duration:** ~45 min
   - **Outcome:** Live web app

## Shared Exercise Output

By end of Notebook 4, all participants populate this table together:
```
publix_agentic_workshop.medallion.gold_store_item_daily
  Columns: store_number, item_id, item_name, item_category, sales_date, units_sold, revenue, line_items
```

In Notebook 5, we query this table as a group. In Notebook 6, the app reads from it.

## Project Structure

```
databricks.yml                         bundle config + dev target
resources/
  medallion.pipeline.yml               SDP: bronze->silver->gold (DAB-managed)
  zerobus_publisher.job.yml            Zerobus publisher job (DAB-managed)
src/
  setup/00_setup.sql                   catalog + schemas (used by Notebook 1)
  zerobus/publisher.py                 Zerobus publisher (reference + generated output)
  pipelines/transformations/
    silver_sales.sql                   streaming clean/typed sales
    gold_store_item_daily.sql          daily units + revenue by store/item (shared output)
labs/
  notebook_1_setup.py                  hand-out: setup + mock data
  notebook_2_kafka_producer.py         hand-out: local Kafka producer
  notebook_3_zerobus_genie_code.py     hand-out: Genie Code guided ingest
  notebook_4_sdp_medallion.py          exercise: medallion pipeline (SDP)
  notebook_5_genie_spaces.py           exercise: Genie agent + Genie One
  notebook_6_build_ship_app.py         exercise: app build + deployment
  PROMPTS.md                           prompt library for Genie Code
```

## Runbook: Deploy for Workshop

### Pre-workshop (instructors / Databricks team)

```bash
# 1. Auth the workshop workspace
databricks auth login --host <workspace-url> -p publix-workshop

# 2. Validate + deploy the bundle (SDP pipeline, Zerobus job, Genie resources)
databricks bundle validate -p publix-workshop
databricks bundle deploy -t dev -p publix-workshop

# 3. Configure Zerobus secrets (client_id, secret, endpoint) in publix_workshop scope
#    (this enables the Zerobus publisher job to run)

# 4. Run the Zerobus publisher to populate initial bronze data
databricks bundle run zerobus_publisher -t dev -p publix-workshop

# 5. Verify gold table has data (after SDP pipeline runs)
databricks sql --warehouse-id <warehouse-id> \
  "SELECT COUNT(*) FROM publix_agentic_workshop.medallion.gold_store_item_daily"
```

### During workshop (participants)

```bash
# Participants run these in order in their workspace:
# 1. Notebook 1 - Setup (creates catalog + tables + mock data)
# 2. Notebook 2 - Kafka producer (optional, if Kafka is available)
# 3. Notebook 3 - Zerobus ingest (use Genie Code to generate publisher)
# 4. Notebook 4 - Medallion pipeline (build silver + gold with SDP)
# 5. Notebook 5 - Genie spaces (create agent on gold table)
# 6. Notebook 6 - Build app (deploy UI via App Builder or CLI)
```

## Notes

- Zerobus endpoint format: `https://<workspace-id>.zerobus.eastus.azuredatabricks.net`.
- Serverless only; Unity Catalog required.
- Bronze tables use Change Data Feed (CDF) so SDP can stream incremental appends.
- All participant notebooks are idempotent (safe to re-run).
- DAB resources (pipeline, jobs, Genie spaces) are version-controlled; deploy once, iterate.
