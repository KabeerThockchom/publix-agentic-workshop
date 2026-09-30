# Publix Agentic Workshop - End-to-End Developer Experience

Complete Databricks agentic workshop delivered as an end-to-end developer experience: from data ingestion (Zerobus) through medallion architecture (Spark Declarative Pipelines) to shipped AI agents and applications.

**Contents:**
- **Notebooks** - 6 hands-on labs covering streaming, medallion architecture, Genie agents, and app deployment
- **Slides** - 15-slide facilitator deck (HTML + React source) covering architecture, use cases, and the agentic workflow (Describe → Generate → Review → Deploy)
- **Reference App** - Publix Store Pulse (FastAPI + React) - a complete example showing lakehouse reads, OLTP writes to Lakebase, and Genie integration

Built and tested in a FEVM Azure Serverless workspace (`eastus`), profile `publix-workshop`.

**The spine:** Spark Declarative Pipelines medallion. All participants build the same gold layer, then query it via Genie agents, and finally ship a production app.

## Workshop Structure

The workshop follows an agentic pattern: **Describe → Generate → Review → Deploy**.

1. **Describe** (Slide 5): Set requirements and constraints in natural language
2. **Generate** (Notebook 3): Use Genie Code to auto-generate data pipelines and ingest logic
3. **Review** (Notebook 4-5): Build medallion architecture and ship a Genie agent
4. **Deploy** (Notebook 6, App): Ship a production web app accessing the lakehouse

## Slides (facilitator-deck)

**Location:** `slides/`

15-slide facilitator deck (HTML + React source) covering:
- **Slide 1-2:** Title, Store Pulse demo (art of the possible)
- **Slide 3-4:** 5-layer architecture, real-world use cases
- **Slide 5:** The agentic workflow (Describe → Generate → Review → Deploy)
- **Slide 6-13:** Module intros (Zerobus, Medallion, Genie, Apps)
- **Slide 14-15:** Take-homes, next steps

**Files:**
- `facilitator-deck.html` - Standalone presentation (Reveal.js), ready to open in any browser
- `publix-agentic-workshop-facilitator-source.tsx` - React source (for open-slide framework)
- `MANIFEST.md` - Full slide inventory and design specs
- `EXPORT_INSTRUCTIONS.md` - How to export to PDF or PPTX

**Design:** Co-branded Publix + Databricks (Navy, Lava, Publix Green, DM Sans typography)

## Reference App (Store Pulse)

**Location:** `app/`

A complete Databricks App (FastAPI + React) demonstrating:
- **Frontend** (React + Vite) - Store performance dashboard, price watch, action panel, Ask Genie
- **Backend** (FastAPI + Lakebase) - SQL warehouse reads, Lakebase OLTP writes, Genie API integration
- **Deployment** - Databricks Apps + Lakebase database resource

**Structure:**
```
app/
  app.py               # FastAPI entry point
  app.yaml             # Databricks App config (warehouse ID, Genie space ID, Lakebase instance)
  requirements.txt     # Python dependencies
  server/              # Backend: config, warehouse queries, Lakebase, Genie API
  frontend/            # React app: components, API client, Tailwind styles
  README.md            # Deployment and architecture guide
```

This is a *reference implementation* — copy, customize, and ship on your own workspace.

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

## Repository Structure

```
publix-agentic-workshop-public/
  README.md                              consolidated overview (this file)
  HANDOFF.md                             participant hand-out summary
  PROMPTS.md                             prompt library for Genie Code
  databricks.yml                         DAB bundle config
  
  labs/                                  participant notebooks
    notebook_1_setup.py                  setup + mock data
    notebook_2_kafka_producer.py         local Kafka producer (optional)
    notebook_3_zerobus_genie_code.py    Genie Code guided ingest
    notebook_4_sdp_medallion.py         medallion pipeline (SDP)
    notebook_5_genie_spaces.py          Genie agents + Genie One
    notebook_6_build_ship_app.py        app build + deployment
  
  resources/                             DAB-managed resources
    medallion.pipeline.yml              SDP pipeline definition
    zerobus_publisher.job.yml           Zerobus publisher job
  
  src/                                   source code (pipelines, publishers)
    zerobus/publisher.py                reference Zerobus publisher
  
  slides/                                facilitator deck + design specs
    facilitator-deck.html               standalone presentation (ready to open)
    publix-agentic-workshop-facilitator-source.tsx  React source
    MANIFEST.md                         slide inventory + design system
    EXPORT_INSTRUCTIONS.md              export to PDF/PPTX
    README.md                           slides guide
  
  app/                                   reference Databricks App
    app.py                              FastAPI entry point
    app.yaml                            App config (warehouse, Genie, Lakebase)
    requirements.txt                    Python deps
    server/                             backend logic
    frontend/                           React UI + Tailwind
    README.md                           app deployment guide
```

## Notes

- **Zerobus endpoint:** `https://<workspace-id>.zerobus.eastus.azuredatabricks.net`
- **Serverless only** with Unity Catalog required
- **Bronze tables** use Change Data Feed (CDF) so SDP can stream incremental appends
- **All participant notebooks** are idempotent (safe to re-run)
- **DAB resources** (pipeline, jobs, Genie spaces) are version-controlled; deploy once, iterate
- **Placeholders:** Real infrastructure IDs (workspace ID, warehouse ID, Genie space ID, Lakebase instance, service principal IDs) have been replaced with `<placeholder>` for safety; update these when deploying to your workspace
