# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ - Genie Space Setup
# MAGIC
# MAGIC This notebook **programmatically creates** an AI/BI Genie Space for the
# MAGIC natural-language "Compare" experience the app embeds:
# MAGIC 1. Builds a `version: 2` serialized space over the 4 materialized views
# MAGIC 2. Adds the customer's sample questions (from `domain.json`) + instructions
# MAGIC 3. Creates the space idempotently and exits with its id (for the app env)
# MAGIC
# MAGIC **Prerequisites:** Run notebooks 01-05 first (01 creates the MVs the space
# MAGIC reads; a `warehouse_id` must be supplied — the DAB passes it in).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

dbutils.widgets.text("catalog", "publix_labor_forecast")
dbutils.widgets.text("schema", "storesight_iq_publix")
dbutils.widgets.text("genie_space_name", "Publix Store Analytics")
dbutils.widgets.text("genie_description", "AI assistant for Publix store operations - labor forecasting, sales, fresh production (deli/bakery), inventory, and curbside.")
# warehouse_id is REQUIRED to create a Genie space — the DAB setup job passes it
# in base_parameters. The other notebooks ignore it.
dbutils.widgets.text("warehouse_id", "77b39aff2611a764")
dbutils.widgets.text("domain_json_path", "")

CATALOG_NAME = dbutils.widgets.get("catalog")
SCHEMA_NAME = dbutils.widgets.get("schema")
GENIE_SPACE_NAME = dbutils.widgets.get("genie_space_name")
GENIE_DESCRIPTION = dbutils.widgets.get("genie_description")
WAREHOUSE_ID = dbutils.widgets.get("warehouse_id")

if not WAREHOUSE_ID:
    raise ValueError(
        "warehouse_id is required to create a Genie space. The DAB passes it via "
        "base_parameters (var.warehouse_id). Set the widget when running manually."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load the domain taxonomy (sample questions come from domain.json)

# COMMAND ----------

# Single source of truth: sample questions are authored per customer in
# domain.yaml -> config/domain.json (same loader the other notebooks use).
import json as _json
import os as _os

def _load_domain():
    cands = []
    _wp = dbutils.widgets.get("domain_json_path")
    if _wp:
        cands.append(_wp)
    cands += [
        "config/domain.json", "../config/domain.json", "./config/domain.json",
        _os.path.join(_os.getcwd(), "config", "domain.json"),
        _os.path.join(_os.path.dirname(_os.getcwd()), "config", "domain.json"),
    ]
    for p in cands:
        try:
            if p and _os.path.exists(p):
                with open(p) as f:
                    return _json.load(f)
        except Exception:
            pass
    return {}

DOMAIN = _load_domain()
SAMPLE_QUESTIONS = DOMAIN.get("genie_sample_questions") or [
    "Which store had the highest sales last week?",
    "Compare the top and bottom store by month-to-date sales",
    "What's the average labor cost percentage by store?",
    "Show stores with the most items below par (low inventory)",
    "Which stores are underperforming this month?",
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Verify the 4 materialized views the space reads

# COMMAND ----------

# The space is grounded on the 4 fast materialized views created in notebook 01
# (NOT the raw tables) — same data the app queries, pre-aggregated.
MVS = ["mv_daily_sales", "mv_employees", "mv_inventory", "mv_store_overview"]

print("Verifying materialized views for the Genie space:")
print("-" * 48)
_missing = []
for _mv in MVS:
    try:
        cnt = spark.sql(f"SELECT COUNT(*) FROM {CATALOG_NAME}.{SCHEMA_NAME}.{_mv}").first()[0]
        print(f"✓ {_mv}: {cnt:,} rows")
    except Exception as e:
        _missing.append(_mv)
        print(f"✗ {_mv}: NOT FOUND - {e}")

if _missing:
    raise RuntimeError(
        f"Materialized views missing: {_missing}. Run notebook 01 first (it creates "
        "the MVs). The Genie space is grounded on these."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Build the serialized space (version 2)

# COMMAND ----------

import json
import uuid

# Serialized-space schema constraints (learned the hard way — all required):
#   - version: 2
#   - data_sources.tables sorted by identifier (order matters)
#   - config.sample_questions[].id = 32-hex; question is a LIST of strings
#   - instructions is an OBJECT ({"text_instructions": [...]}), NOT an array;
#     each text_instruction has a 32-hex id + content as a LIST of strings
tables = [
    {"identifier": f"{CATALOG_NAME}.{SCHEMA_NAME}.{m}"} for m in sorted(MVS)
]

sample_questions = [
    {"id": uuid.uuid4().hex, "question": [q]} for q in SAMPLE_QUESTIONS
]

instructions = {
    "text_instructions": [
        {
            "id": uuid.uuid4().hex,
            "content": [
                f"You are an AI assistant for {GENIE_SPACE_NAME}. Answer using the "
                f"materialized views in {CATALOG_NAME}.{SCHEMA_NAME}: "
                "mv_store_overview (per-store sales KPIs, rankings, staffing and "
                "inventory rollups), mv_daily_sales (sales by store/date/channel), "
                "mv_employees (staffing roster), and mv_inventory (stock vs par). "
                "Reference specific store names and cities, give percentages and "
                "comparisons, and keep answers concise."
            ],
        }
    ]
}

serialized_space = {
    "version": 2,
    "config": {"sample_questions": sample_questions},
    "data_sources": {"tables": tables},
    "instructions": instructions,
}

print("Serialized space built:")
print(f"  tables: {[t['identifier'] for t in tables]}")
print(f"  sample_questions: {len(sample_questions)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create the Genie space (idempotent) and export its id

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Create/list via the REST API directly (w.api_client.do) rather than the SDK
# helper methods: some runtime SDK builds' GenieAPI lacks create_space/
# list_spaces (AttributeError: 'GenieAPI' object has no attribute 'create_space'),
# whereas the REST endpoint /api/2.0/genie/spaces is stable across versions.
_GENIE_SPACES = "/api/2.0/genie/spaces"

# Idempotent: if a space with this exact title already exists, reuse it rather
# than creating duplicates on re-run (`run-now --only setup_genie_space`).
existing_id = None
try:
    _page_token = None
    while True:
        _q = {"page_token": _page_token} if _page_token else None
        _resp = w.api_client.do("GET", _GENIE_SPACES, query=_q) or {}
        for space in (_resp.get("spaces") or []):
            if space.get("title") == GENIE_SPACE_NAME:
                existing_id = space.get("space_id") or space.get("id")
                break
        _page_token = _resp.get("next_page_token")
        if existing_id or not _page_token:
            break
except Exception as e:
    print(f"(could not list existing spaces: {e})")

if existing_id:
    space_id = existing_id
    print(f"✓ Reusing existing Genie space '{GENIE_SPACE_NAME}': {space_id}")
else:
    created = w.api_client.do("POST", _GENIE_SPACES, body={
        "warehouse_id": WAREHOUSE_ID,
        "serialized_space": json.dumps(serialized_space),
        "title": GENIE_SPACE_NAME,
        "description": GENIE_DESCRIPTION,
    }) or {}
    space_id = created.get("space_id") or created.get("id")
    print(f"✓ Created Genie space '{GENIE_SPACE_NAME}': {space_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("=" * 60)
print("Genie Space ready!")
print("=" * 60)
print(f"""
  Name:        {GENIE_SPACE_NAME}
  Space ID:    {space_id}
  Warehouse:   {WAREHOUSE_ID}
  Grounded on: {CATALOG_NAME}.{SCHEMA_NAME}.(mv_daily_sales, mv_employees, mv_inventory, mv_store_overview)

The wiring step sets GENIE_SPACE_ID={space_id} on the app (env / app resource).

Next: notebook 07_setup_streaming_job.py
""")
print("=" * 60)

# The DAB / wiring reads this exit value to set GENIE_SPACE_ID on the app.
dbutils.notebook.exit(space_id or "")
