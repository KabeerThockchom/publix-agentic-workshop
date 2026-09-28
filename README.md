# Publix Agentic Development Workshop - Notebooks

Take-home notebooks and prompts from the Publix "Agentic Development on Databricks"
workshop. Everything here is built with **Genie Code**: describe what you want, let it
generate and plan, review, deploy.

These are prompt-first. Each lab hands you the Genie Code prompt to type, with a reference
solution as backup. The point is the workflow, not the copy-paste.

## What's inside

```
labs/
  lab_00_setup.py                     orientation + the vibe-coding loop + a warm-up prompt
  lab_01_zerobus_realtime_ingest.py   real-time ingest with Zerobus
  lab_02_sdp_medallion.py             bronze -> silver -> gold with Spark Declarative Pipelines
  lab_03_genie_spaces.py              stand up a Genie space + Genie One
  lab_04_genie_code_cli_app.py        build and ship a Databricks App from the CLI
  PROMPTS.md                          a copy-paste Genie Code prompt playbook
src/                                  reference solutions (setup SQL, publisher, pipeline SQL)
resources/                            Asset Bundle resource defs (pipeline + job)
databricks.yml                        Asset Bundle config
```

## Prerequisites

- A Databricks workspace with Unity Catalog and a serverless SQL warehouse.
- The Databricks CLI, authenticated to your workspace.
- For the Zerobus lab: `pip install databricks-zerobus-ingest-sdk` and a service principal
  with insert access on the target tables.

Anywhere you see `<workspace-id>`, `<service-principal-app-id>`, or `<warehouse-id>`, swap in
your own values.

## How to use

1. Import `labs/` into your workspace (or open them from a Git folder).
2. Start with `lab_00_setup`, then work through 1 to 4.
3. Keep `PROMPTS.md` open and prompt Genie Code as you go.

## The loop, every time

Describe → Generate → **Review** (read the plan, open a PR, keep a human in the loop) → Deploy.

## Related

The Vibe-to-Value app (business-user, prompt-to-app) is a separate project:
https://github.com/databricks-solutions/vibe-coding-workshop-app
