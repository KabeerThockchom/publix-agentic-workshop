# AGENTS.md - Publix Agentic Workshop

Assistant instructions for Genie Code in this repo. Follow these in every generation.

## Per-participant namespace (read first)

Everyone builds in one shared workspace, so every participant works in their own namespace. At the
start of a session, establish the participant's token `<yourname>` (lowercase, no spaces). If it is
not already stated, ask once, or derive it from `SELECT current_user()` (the part before `@`,
lowercased, dots to underscores). Then apply it to **every** object you create, without being
reminded:

- **Medallion track** (`labs/`): shared catalog `publix_technology`, schema `agentic_ai_training_<yourname>` (all layers in one schema).
- **Flagship track** (`FLAGSHIP_PROMPTS.md`): shared catalog `publix_technology`, schema `storesight_iq_<yourname>`.
- **Workspace-global names must carry the suffix** - they collide across participants otherwise:
  - Model Serving endpoints -> `storesight-<model>-<yourname>`
  - Genie space -> `"Publix Store Analytics - <yourname>"`
  - Databricks App -> `store-labor-planner-<yourname>`

Never write a hardcoded `storesight_iq_publix` or `publix_agentic_workshop` into a participant's
objects. Those are reference/example names only.

## Databricks conventions

- Always use the three-level namespace `catalog.schema.table`. Never `hive_metastore`.
- Pipelines are **Spark Declarative Pipelines in SQL**, serverless, with `CLUSTER BY` (liquid
  clustering) - no `PARTITION BY`.
- Streaming tables use `CREATE OR REFRESH STREAMING TABLE` with `EXPECT (...) ON VIOLATION DROP ROW`
  on the **aliased output columns**, not raw source paths.
- Gold layers are materialized views over silver.
- Add table and column `COMMENT`s; tag PII where relevant.

## Delivery

- Nothing deploys outside the Databricks Asset Bundle (`databricks.yml` + `resources/`) and the
  service-principal automation. Generate the DAB resource block, not manual UI steps.
- Show the plan and the code; keep a human in the loop before `databricks bundle deploy`.
