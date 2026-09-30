# Publix Agentic Development Workshop - Handoff

Take-home materials for the Publix "Agentic End-to-End Developer Experience" workshop.
Everything here is built with **Genie Code**: describe what you want, review the plan, deploy.

## Hand-out notebooks (run in order)

1. `labs/notebook_1_setup.py` - create catalogs, schemas, tables + mock data (run this first, on your side).
2. `labs/notebook_2_kafka_producer.py` - a local Kafka producer, run on your laptop (optional; Zerobus is the no-Kafka path).
3. `labs/notebook_3_zerobus_genie_code.py` - real-time ingest built with Genie Code.
4. `labs/notebook_4_sdp_medallion.py` - bronze -> silver -> gold with Spark Declarative Pipelines (everyone lands in the same shared gold table).
5. `labs/notebook_5_genie_spaces.py` - metric views + a Genie space/agent (created programmatically via the API).
6. `labs/notebook_6_build_ship_app.py` - build + ship a Databricks App (App Builder or CLI).

Plus `labs/PROMPTS.md` (the Genie Code prompt playbook) and `README.md`.

## What Publix needs to have ready

- A training workspace with **Genie Code enabled** and a **serverless SQL warehouse**.
- Each participant can **create schemas + tables and load data** in a catalog.
- The Databricks CLI authenticated to the workspace.
- Anywhere you see `<workspace-id>`, `<service-principal-app-id>`, `<warehouse-id>`, `<genie-space-id>`, swap in your own values.

## Reference apps (art of the possible + take-home)

- **Store Pulse** - the flagship "art of the possible" app: real-time sales + price feed, a refund / what-if action panel on Lakebase, and an embedded Genie agent, all on the governed gold + metric views. Shown at the start, then decomposed across the day.
- **Build Studio** - the take-home app: describe an idea in plain language and get the Genie Code prompts to build a pipeline + Lakebase + Genie agents + app. Deployed in your workspace, it drives ongoing adoption.

## The loop, every time

Describe -> Generate -> **Review** (read the plan, open a PR, keep a human in the loop) -> Deploy.
