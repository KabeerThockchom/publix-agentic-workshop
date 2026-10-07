# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ - Streaming Job Setup
# MAGIC 
# MAGIC This notebook sets up a Databricks Job that:
# MAGIC 1. Simulates real-time POS transaction streaming
# MAGIC 2. Writes to Lakebase for OLTP access
# MAGIC 3. Maintains Delta streaming tables for analytics
# MAGIC 
# MAGIC **Prerequisites:** Run notebooks 01-06 first

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

dbutils.widgets.text("catalog", "publix_technology")
dbutils.widgets.text("schema", "storesight_iq_publix")
dbutils.widgets.text("resource_prefix", "storesight-publix")
dbutils.widgets.text("lakebase_database", "databricks_postgres")
# warehouse_id: MV REFRESH runs on a SQL warehouse (not serverless generic).
dbutils.widgets.text("warehouse_id", "77b39aff2611a764")
dbutils.widgets.text("domain_json_path", "")

CATALOG_NAME = dbutils.widgets.get("catalog")
SCHEMA_NAME = dbutils.widgets.get("schema")
PREFIX = dbutils.widgets.get("resource_prefix")
WAREHOUSE_ID = dbutils.widgets.get("warehouse_id")
JOB_NAME = f"{PREFIX}-streaming-simulator"
LAKEBASE_INSTANCE = f"{PREFIX}-oltp"
LAKEBASE_DATABASE = dbutils.widgets.get("lakebase_database")

# Load domain taxonomy for store count (config/domain.json)
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
    return {"stores": [None] * 25}

NUM_STORES = len(_load_domain().get("stores", []) or [None] * 25)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create Streaming Simulation Notebook
# MAGIC 
# MAGIC First, we'll create a notebook that simulates POS transactions and can be run as a job.

# COMMAND ----------

# Build notebook content using cell separator variable to avoid Databricks parsing issues
# (Databricks interprets "# COMMAND ----------" as cell breaks even inside strings)
CELL_SEP = "# COMMAND " + "-" * 10

streaming_notebook_content = f"""# Databricks notebook source
# MAGIC %md
# MAGIC # POS Transaction Streaming Simulator
# MAGIC This notebook generates simulated real-time POS transactions.

{CELL_SEP}

from datetime import datetime, timedelta
import random
import time
import uuid
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

# Configuration
CATALOG = "{CATALOG_NAME}"
SCHEMA = "{SCHEMA_NAME}"
NUM_STORES = {NUM_STORES}
BATCH_SIZE = 10  # Transactions per batch
BATCH_INTERVAL = 5  # Seconds between batches

# Define schema to match Delta table exactly (avoids type mismatch errors)
TXN_SCHEMA = StructType([
    StructField("txn_id", StringType(), True),
    StructField("store_id", IntegerType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("total", DoubleType(), True),
    StructField("channel", StringType(), True),
    StructField("payment_method", StringType(), True),
    StructField("item_count", IntegerType(), True),
])

{CELL_SEP}

# Neutral menu items for transaction generation (id, name, medium_price, large_price)
MENU_ITEMS = [
    (1, "Signature Item A", 15.99, 18.99),
    (2, "Signature Item B", 13.99, 16.99),
    (3, "Signature Item C", 12.99, 15.99),
    (4, "Signature Item D", 15.99, 18.99),
    (5, "Signature Item E", 14.49, 17.49),
    (6, "Signature Item F", 15.49, 18.49),
    (7, "Signature Item G", 16.99, 19.99),
    (8, "Signature Item H", 16.49, 19.49),
    (9, "Side Item", 6.49, 6.49),
    (10, "Combo Item", 7.99, 7.99),
]

CHANNELS = ["in_store", "delivery", "app", "third_party"]
PAYMENTS = ["credit", "debit", "cash", "apple_pay"]

{CELL_SEP}

def generate_transaction():
    \"\"\"Generate a single simulated transaction.\"\"\"
    store_id = int(random.randint(1, NUM_STORES))  # Explicit int cast
    now = datetime.now()
    
    # Random items
    num_items = int(random.randint(1, 3))  # Explicit int cast
    items = random.sample(MENU_ITEMS, num_items)
    
    total = sum(
        item[3] if random.random() > 0.4 else item[2]
        for item in items
    )
    
    # Add sides
    if random.random() > 0.5:
        total += 1.99 + 2.49
    
    return (
        str(uuid.uuid4())[:8],      # txn_id
        store_id,                    # store_id (INT)
        now,                         # timestamp
        float(round(total, 2)),      # total (DOUBLE)
        random.choice(CHANNELS),     # channel
        random.choice(PAYMENTS),     # payment_method
        num_items,                   # item_count (INT)
    )

{CELL_SEP}

# Main streaming loop
print(f"Starting POS streaming simulation...")
print(f"Generating {{BATCH_SIZE}} transactions every {{BATCH_INTERVAL}} seconds")
print("Press Stop to halt the simulation")

batch_count = 0

while True:
    # Generate batch of transactions as tuples (for schema matching)
    transactions = [generate_transaction() for _ in range(BATCH_SIZE)]
    
    # Convert to DataFrame with explicit schema
    df = spark.createDataFrame(transactions, schema=TXN_SCHEMA)
    df.write.mode("append").saveAsTable(f"{{CATALOG}}.{{SCHEMA}}.pos_transactions_stream")
    
    batch_count += 1
    print(f"[{{datetime.now().strftime('%H:%M:%S')}}] Batch {{batch_count}}: {{BATCH_SIZE}} transactions")
    
    time.sleep(BATCH_INTERVAL)
"""

# Save the streaming notebook
import base64
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat, Language

w = WorkspaceClient()

# Get current user for path
current_user = spark.sql("SELECT current_user()").first()[0]
notebook_path = f"/Users/{current_user}/{PREFIX.replace('-','_')}_streaming_simulator"

print(f"Creating notebook at: {notebook_path}")

try:
    w.workspace.import_(
        path=notebook_path,
        content=base64.b64encode(streaming_notebook_content.encode()).decode(),
        format=ImportFormat.SOURCE,
        language=Language.PYTHON,
        overwrite=True
    )
    print(f"✓ Created streaming notebook: {notebook_path}")
except Exception as e:
    print(f"⚠ Could not create notebook automatically: {e}")
    print("\n" + "="*60)
    print("MANUAL NOTEBOOK CREATION REQUIRED")
    print("="*60)
    print(f"\n1. Go to Workspace > Users > {current_user}")
    print(f"2. Click '⋮' > Create > Notebook")
    print(f"3. Name it: {PREFIX.replace('-','_')}_streaming_simulator")
    print(f"4. Language: Python")
    print(f"5. Copy the content below into the notebook:\n")
    print("-"*60)
    print(streaming_notebook_content)
    print("-"*60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create the Streaming Table

# COMMAND ----------

# Create streaming table schema
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.pos_transactions_stream (
    txn_id STRING,
    store_id INT,
    timestamp TIMESTAMP,
    total DOUBLE,
    channel STRING,
    payment_method STRING,
    item_count INT
)
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true'
)
""")

print(f"✓ Created streaming table: {CATALOG_NAME}.{SCHEMA_NAME}.pos_transactions_stream")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create Databricks Job

# COMMAND ----------

from databricks.sdk.service.jobs import Task, NotebookTask, JobSettings

# Job configuration - using serverless compute
job_config = JobSettings(
    name=JOB_NAME,
    tasks=[
        Task(
            task_key="streaming_simulator",
            notebook_task=NotebookTask(
                notebook_path=notebook_path
            ),
            # No cluster specified = serverless compute
            timeout_seconds=0,  # No timeout - continuous
        )
    ],
    max_concurrent_runs=1,
)

# Create or update job
try:
    # Check if job exists
    existing_jobs = w.jobs.list(name=JOB_NAME)
    existing = next((j for j in existing_jobs if j.settings.name == JOB_NAME), None)
    
    if existing:
        w.jobs.reset(job_id=existing.job_id, new_settings=job_config)
        job_id = existing.job_id
        print(f"✓ Updated job: {JOB_NAME} (ID: {job_id})")
    else:
        job = w.jobs.create(**job_config.as_dict())
        job_id = job.job_id
        print(f"✓ Created job: {JOB_NAME} (ID: {job_id})")
        
except Exception as e:
    print(f"Error creating job: {e}")
    print("\nTo create manually:")
    print(f"1. Go to Workflows > Jobs > Create Job")
    print(f"2. Name: {JOB_NAME}")
    print(f"3. Task: Run notebook {notebook_path}")
    print(f"4. Compute: Serverless")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Start the Streaming Job

# COMMAND ----------

# MAGIC %md
# MAGIC ### To start the streaming simulation:
# MAGIC 
# MAGIC **Option A: Run the job continuously**
# MAGIC ```python
# MAGIC w.jobs.run_now(job_id=job_id)
# MAGIC ```
# MAGIC 
# MAGIC **Option B: Run from the Jobs UI**
# MAGIC 1. Go to Workflows > Jobs
# MAGIC 2. Find the "{PREFIX}-streaming-simulator" job
# MAGIC 3. Click "Run Now"
# MAGIC 
# MAGIC **Option C: Schedule the job**
# MAGIC Configure a schedule in the job settings to run during demo hours.
# MAGIC 
# MAGIC **Note:** The job will run continuously until stopped. For demos, you can run it manually when needed.

# COMMAND ----------

# Optionally start the job now
START_JOB_NOW = False  # Set to True to start immediately

if START_JOB_NOW:
    try:
        run = w.jobs.run_now(job_id=job_id)
        print(f"✓ Started job run: {run.run_id}")
        print(f"  Monitor at: {w.config.host}/#job/{job_id}/run/{run.run_id}")
    except Exception as e:
        print(f"Could not start job: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Refresh materialized views (staleness note)

# COMMAND ----------

# The 4 materialized views created in notebook 01 (mv_daily_sales, mv_employees,
# mv_inventory, mv_store_overview) are point-in-time snapshots and do NOT
# auto-update. Two things to know:
#   • This streaming simulator writes to a SEPARATE table
#     (`pos_transactions_stream`), which the MVs do NOT read — so running the
#     sim does not by itself make the MVs stale.
#   • The MVs DO go stale if you reload/regenerate the batch tables
#     (re-run notebook 01) or change `stores_kpi_view`. After any such change,
#     REFRESH them (below). If you wire the stream into the batch tables, or run
#     continuously, schedule a periodic REFRESH.
_MVS_TO_REFRESH = ["mv_daily_sales", "mv_employees", "mv_inventory", "mv_store_overview"]
# MV REFRESH is only allowed on a SQL warehouse (not serverless generic compute),
# so route it through the Statement Execution API. Non-fatal: the streaming sim
# writes to a separate table that the MVs don't read, so a refresh failure here
# doesn't block the demo.
if not WAREHOUSE_ID:
    print("⚠ no warehouse_id — skipping MV refresh (runs on a SQL warehouse).")
else:
    from databricks.sdk import WorkspaceClient as _WC
    from databricks.sdk.service.sql import StatementState as _SS
    import time as _time
    _wh = _WC()
    for _mv in _MVS_TO_REFRESH:
        try:
            _r = _wh.statement_execution.execute_statement(
                warehouse_id=WAREHOUSE_ID,
                statement=f"REFRESH MATERIALIZED VIEW {CATALOG_NAME}.{SCHEMA_NAME}.{_mv}",
                wait_timeout="50s")
            while _r.status and _r.status.state in (_SS.PENDING, _SS.RUNNING):
                _time.sleep(3); _r = _wh.statement_execution.get_statement(_r.statement_id)
            print(f"✓ Refreshed {_mv}")
        except Exception as e:
            print(f"⚠ Could not refresh {_mv}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("=" * 60)
print("Streaming Job Setup Complete!")
print("=" * 60)
print(f"""
Created:
  • Streaming notebook: {notebook_path}
  • Streaming table: {CATALOG_NAME}.{SCHEMA_NAME}.pos_transactions_stream
  • Job: {JOB_NAME}

To start streaming:
  1. Go to Workflows > Jobs
  2. Find '{JOB_NAME}'
  3. Click 'Run Now'

The job will generate ~2 transactions/second, simulating 
real-time POS data from all 25 stores.

Stop the job when not demoing to save compute costs.
""")
print("=" * 60)
print("\n✓ All Databricks setup notebooks complete!")
print("\nNext steps:")
print("  1. Add GENIE_SPACE_ID to your .env file")
print("  2. Start the streaming job (optional)")
print("  3. Run the StoreSight IQ app locally")
print("=" * 60)

