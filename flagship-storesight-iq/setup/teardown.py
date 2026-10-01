# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ — Teardown
# MAGIC
# MAGIC Removes everything the setup job + wiring created, so the demo can be rebuilt
# MAGIC from zero. **Idempotent and safe to re-run** — every delete is guarded with
# MAGIC `IF EXISTS` / ignore-if-missing, so running it twice (or on a partially set-up
# MAGIC workspace) is harmless.
# MAGIC
# MAGIC **What this removes** (the imperatively-created resources the bundle doesn't own):
# MAGIC - the 4 model serving endpoints (created by notebooks 02–05)
# MAGIC - the streaming job + its generated simulator notebook (notebook 07)
# MAGIC - the Genie space (notebook 06)
# MAGIC - the Unity Catalog **schema** and everything in it — tables, views,
# MAGIC   materialized views, and registered models (`DROP SCHEMA … CASCADE`)
# MAGIC
# MAGIC **What it does NOT touch** (owned by the user, not created by setup): the Unity
# MAGIC Catalog itself and the Lakebase instance — both are prerequisites, reused across
# MAGIC rebuilds. (The app's Lakebase state table is recreated on next startup.)
# MAGIC
# MAGIC **Full teardown = this notebook, then `databricks bundle destroy`** (which removes
# MAGIC the bundle-managed resources: the setup job, this teardown job, the app, and the
# MAGIC now-empty schema resource). See `setup/README.md`.

# COMMAND ----------

# Naming is passed by the bundle teardown job (base_parameters); the defaults are
# rewritten per-customer by accelerator/generate.py so a standalone run also works.
dbutils.widgets.text("catalog", "publix_labor_forecast")
dbutils.widgets.text("schema", "storesight_iq_publix")
dbutils.widgets.text("resource_prefix", "storesight-publix")
dbutils.widgets.text("genie_space_name", "Publix Store Analytics")

CATALOG_NAME = dbutils.widgets.get("catalog")
SCHEMA_NAME = dbutils.widgets.get("schema")
PREFIX = dbutils.widgets.get("resource_prefix")
GENIE_SPACE_NAME = dbutils.widgets.get("genie_space_name")

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
removed, skipped = [], []

# COMMAND ----------

# MAGIC %md ## 1. Delete the 4 model serving endpoints (notebooks 02–05)

# COMMAND ----------

for _suffix in ("demand-forecast", "labor-optimizer", "inventory-predictor", "prep-scheduler"):
    _ep = f"{PREFIX}-{_suffix}"
    try:
        w.serving_endpoints.delete(name=_ep)
        removed.append(f"serving endpoint {_ep}")
        print(f"✓ deleted serving endpoint {_ep}")
    except Exception:
        skipped.append(f"serving endpoint {_ep} (absent)")
        print(f"· serving endpoint {_ep} not present — skipping")

# COMMAND ----------

# MAGIC %md ## 2. Delete the streaming job + its generated simulator notebook (notebook 07)

# COMMAND ----------

_job_name = f"{PREFIX}-streaming-simulator"
_found_job = False
for _j in w.jobs.list(name=_job_name):
    _found_job = True
    try:
        w.jobs.delete(job_id=_j.job_id)
        removed.append(f"job {_job_name} ({_j.job_id})")
        print(f"✓ deleted job {_job_name} ({_j.job_id})")
    except Exception as _e:
        skipped.append(f"job {_job_name} ({_e})")
        print(f"· could not delete job {_job_name}: {_e}")
if not _found_job:
    skipped.append(f"job {_job_name} (absent)")
    print(f"· job {_job_name} not present — skipping")

try:
    _user = w.current_user.me().user_name
    _nb = f"/Users/{_user}/{PREFIX.replace('-', '_')}_streaming_simulator"
    w.workspace.delete(path=_nb)
    removed.append(f"notebook {_nb}")
    print(f"✓ deleted simulator notebook {_nb}")
except Exception:
    skipped.append("streaming simulator notebook (absent)")
    print("· streaming simulator notebook not present — skipping")

# COMMAND ----------

# MAGIC %md ## 3. Delete the Genie space by title (notebook 06)

# COMMAND ----------

try:
    _sid = None
    for _s in w.genie.list_spaces():
        if getattr(_s, "title", None) == GENIE_SPACE_NAME:
            _sid = _s.space_id if hasattr(_s, "space_id") else getattr(_s, "id", None)
            break
    if _sid:
        if hasattr(w.genie, "delete_space"):
            w.genie.delete_space(_sid)
        else:
            w.api_client.do("DELETE", f"/api/2.0/genie/spaces/{_sid}")
        removed.append(f"genie space '{GENIE_SPACE_NAME}' ({_sid})")
        print(f"✓ deleted Genie space '{GENIE_SPACE_NAME}' ({_sid})")
    else:
        skipped.append(f"genie space '{GENIE_SPACE_NAME}' (absent)")
        print(f"· Genie space '{GENIE_SPACE_NAME}' not present — skipping")
except Exception as _e:
    skipped.append(f"genie space '{GENIE_SPACE_NAME}' ({_e})")
    print(f"· could not delete Genie space: {_e}")

# COMMAND ----------

# MAGIC %md ## 4. Drop the Unity Catalog schema — tables, views, MVs, registered models

# COMMAND ----------

# DROP SCHEMA ... CASCADE removes every table, view, materialized view, and
# UC-registered model the setup job created under this schema. IF EXISTS makes it
# safe when the schema is already gone. The parent CATALOG is a prerequisite and is
# intentionally left in place.
spark.sql(f"DROP SCHEMA IF EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}` CASCADE")
removed.append(f"schema {CATALOG_NAME}.{SCHEMA_NAME} (CASCADE)")
print(f"✓ dropped schema {CATALOG_NAME}.{SCHEMA_NAME} (CASCADE)")

# COMMAND ----------

# MAGIC %md ## Summary

# COMMAND ----------

print("Teardown complete.\n")
print("Removed:")
for _r in removed:
    print(f"  ✓ {_r}")
if skipped:
    print("\nAlready absent (skipped — safe):")
    for _s in skipped:
        print(f"  · {_s}")
print(
    "\nNext: `databricks bundle destroy -t dev -p <profile> --auto-approve` removes the "
    "bundle-managed resources (setup job, teardown job, app, empty schema resource). "
    "Then the workspace is back to a clean state."
)
