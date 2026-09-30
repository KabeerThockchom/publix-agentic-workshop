# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 3 - Real-Time Ingest with Zerobus (via Genie Code)
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** Build a real-time publisher using Genie Code that streams Publix events into your bronze tables via Zerobus.
# MAGIC This is a **guided code generation** exercise - you describe what you want, Genie Code writes it, you deploy it.
# MAGIC
# MAGIC **Why Zerobus?** Serverless push API - no Kafka cluster, no topics to manage. Events land directly in Delta tables.
# MAGIC
# MAGIC **Duration:** ~20 minutes (generate + review + test).

# COMMAND ----------

# MAGIC %md
# MAGIC ## What is Zerobus?
# MAGIC
# MAGIC **Zerobus** is a serverless ingest service on Databricks:
# MAGIC
# MAGIC - **Serverless** - Databricks manages the infrastructure
# MAGIC - **Push API** - Applications push events via gRPC/REST; Zerobus lands them in Delta
# MAGIC - **Real-time** - Events arrive in seconds, not batches
# MAGIC - **Governed** - Fully integrated with Unity Catalog; all lineage tracked
# MAGIC
# MAGIC **For Publix:**
# MAGIC - POS systems, item masters, or pricing systems push events to the Zerobus endpoint
# MAGIC - Events are validated and written directly to `bronze.sales_events` or `bronze.price_updates`
# MAGIC - No intermediate Kafka topics, no consumer lag
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Architecture Recap
# MAGIC
# MAGIC ```
# MAGIC Publix POS / Item System
# MAGIC           |
# MAGIC           v (push via gRPC/REST)
# MAGIC    Zerobus Endpoint
# MAGIC           |
# MAGIC           v (writes with UC lineage)
# MAGIC    bronze.sales_events / bronze.price_updates (Delta, Change Data Feed enabled)
# MAGIC           |
# MAGIC           v (Notebook 4: SDP streams)
# MAGIC    medallion.silver_sales (streaming table)
# MAGIC           |
# MAGIC           v (aggregates)
# MAGIC    medallion.gold_store_item_daily (materialized view, queried by Genie)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Your Zerobus Workspace Context
# MAGIC
# MAGIC This workshop is set up with a **known Zerobus workspace**. Configuration is pre-baked:
# MAGIC
# MAGIC | Parameter | Value |
# MAGIC |-----------|-------|
# MAGIC | Workspace ID | `<workspace-id>` |
# MAGIC | Zerobus Endpoint | `https://<workspace-id>.zerobus.eastus.azuredatabricks.net` |
# MAGIC | Secret Scope | `publix_workshop` |
# MAGIC | Service Principal | app_id `<service-principal-app-id>` (INSERT on bronze tables) |
# MAGIC | Publisher Job | `resources/zerobus_publisher.job.yml` (DAB-managed) |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Generate the Publisher with Genie Code
# MAGIC
# MAGIC Open **Genie Code** (Cmd/Ctrl + I) and copy-paste this prompt:
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Build a Python Zerobus publisher for Databricks. It should:
# MAGIC > - Use the Zerobus Ingest SDK (install: pip install databricks-zerobus-ingest-sdk)
# MAGIC > - Connect to the Zerobus endpoint: https://<workspace-id>.zerobus.eastus.azuredatabricks.net
# MAGIC > - Authenticate using a service principal (app_id and secret from Databricks secret scope publix_workshop)
# MAGIC > - Define two Zerobus streams:
# MAGIC >   1. publix_agentic_workshop.bronze.sales_events (6 realistic Publix products with prices)
# MAGIC >   2. publix_agentic_workshop.bronze.price_updates
# MAGIC > - For 60 seconds, publish synthetic events:
# MAGIC >   - 3-6 sales per second to sales_events (random store, product, quantity)
# MAGIC >   - Occasional price updates (10% chance per second)
# MAGIC > - Use fire-and-forget ingestion (ingest_record_nowait)
# MAGIC > - Flush and close streams cleanly at the end
# MAGIC > - Use environment variables for all credentials (DATABRICKS_WORKSPACE_URL, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET, ZEROBUS_SERVER_ENDPOINT, DURATION_SECONDS)
# MAGIC >
# MAGIC > Generate a production-ready script. Show me the plan and the code.
# MAGIC > ```
# MAGIC
# MAGIC Genie Code will generate the publisher. Review the plan, then save the code to `src/zerobus/publisher.py`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reference Solution
# MAGIC
# MAGIC Below is the **tested reference implementation** we ship with the workshop.
# MAGIC Compare your Genie Code output against this - they should be very similar.

# COMMAND ----------

# reference solution (src/zerobus/publisher.py)
reference_code = '''"""Lab 3 - Zerobus synthetic publisher.

Pumps synthetic Publix sales + price-update events into the bronze Delta tables
via the Zerobus Ingest SDK, so the real-time lab runs live without a Kafka topic.

Config comes from environment / job parameters (no secrets in code):
  ZEROBUS_SERVER_ENDPOINT   e.g. https://<workspace-id>.zerobus.eastus.azuredatabricks.net
  DATABRICKS_WORKSPACE_URL  e.g. https://adb-<id>.<n>.azuredatabricks.net
  DATABRICKS_CLIENT_ID      service principal application id (INSERT on the bronze tables)
  DATABRICKS_CLIENT_SECRET  service principal secret
  DURATION_SECONDS          how long to publish (default 60)

Install: pip install databricks-zerobus-ingest-sdk
"""

import os
import random
import time
from datetime import datetime
from uuid import uuid4

from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

CATALOG = os.environ.get("WORKSHOP_CATALOG", "publix_agentic_workshop")
SALES_TABLE = f"{CATALOG}.bronze.sales_events"
PRICE_TABLE = f"{CATALOG}.bronze.price_updates"

SERVER_ENDPOINT = os.environ["ZEROBUS_SERVER_ENDPOINT"]
WORKSPACE_URL = os.environ["DATABRICKS_WORKSPACE_URL"]
CLIENT_ID = os.environ["DATABRICKS_CLIENT_ID"]
CLIENT_SECRET = os.environ["DATABRICKS_CLIENT_SECRET"]
DURATION_SECONDS = int(os.environ.get("DURATION_SECONDS", "60"))

STORE_NUMBERS = [100, 102, 104, 106, 108, 110, 112, 114]
PRODUCTS = [
    {"id": 1001, "name": "Boar\\'s Head Deli Ham", "category": "Deli", "price": 6.99},
    {"id": 1002, "name": "Publix Bakery Bread", "category": "Bakery", "price": 2.49},
    {"id": 1003, "name": "GreenWise Organic Milk", "category": "Dairy", "price": 4.29},
    {"id": 1004, "name": "Coca-Cola 12-pack", "category": "Beverage", "price": 6.49},
    {"id": 1005, "name": "Publix Deli Sub", "category": "Deli", "price": 7.99},
    {"id": 1006, "name": "Fresh Strawberries", "category": "Produce", "price": 3.99},
]


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def main() -> None:
    sdk = ZerobusSdk(SERVER_ENDPOINT, WORKSPACE_URL)
    options = StreamConfigurationOptions(record_type=RecordType.JSON)

    sales = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, TableProperties(SALES_TABLE), options)
    prices = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, TableProperties(PRICE_TABLE), options)

    print(f"[*] Publishing synthetic Publix events for {DURATION_SECONDS}s -> {SALES_TABLE}")
    start, count = time.time(), 0
    try:
        while time.time() - start < DURATION_SECONDS:
            now = _now()
            for _ in range(random.randint(3, 6)):
                p = random.choice(PRODUCTS)
                qty = random.randint(1, 10)
                sales.ingest_record_nowait({
                    "event_id": str(uuid4()),
                    "store_number": random.choice(STORE_NUMBERS),
                    "event_timestamp": now,
                    "item_id": p["id"],
                    "item_name": p["name"],
                    "item_category": p["category"],
                    "quantity_sold": qty,
                    "unit_price": float(p["price"]),
                    "total_amount": round(p["price"] * qty, 2),
                    "cashier_id": f"C{random.randint(1000, 9999)}",
                    "transaction_id": f"TX{uuid4().hex[:12]}",
                    "ingestion_time": now,
                })
                count += 1
            if random.random() < 0.1:  # occasional price change
                p = random.choice(PRODUCTS)
                new_price = round(p["price"] * random.uniform(0.95, 1.05), 2)
                prices.ingest_record_nowait({
                    "event_id": str(uuid4()),
                    "event_timestamp": now,
                    "item_id": p["id"],
                    "item_name": p["name"],
                    "old_price": float(p["price"]),
                    "new_price": new_price,
                    "effective_date": datetime.utcnow().date().isoformat(),
                    "ingestion_time": now,
                })
            time.sleep(1)
        sales.flush()
        prices.flush()
        print(f"[OK] Published {count} sales events.")
    finally:
        sales.close()
        prices.close()


if __name__ == "__main__":
    main()
'''

print("Reference publisher (src/zerobus/publisher.py):")
print(reference_code[:500] + "...\n[See full code above]")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy the Publisher as a DAB Job
# MAGIC
# MAGIC Once your Genie Code output is saved to `src/zerobus/publisher.py`, the DAB job definition
# MAGIC (`resources/zerobus_publisher.job.yml`) is already configured to run it.
# MAGIC
# MAGIC To deploy and run:
# MAGIC
# MAGIC ```bash
# MAGIC # 1. Validate the bundle
# MAGIC databricks bundle validate -p publix-workshop
# MAGIC
# MAGIC # 2. Deploy (creates the job)
# MAGIC databricks bundle deploy -t dev -p publix-workshop
# MAGIC
# MAGIC # 3. Run the publisher job
# MAGIC databricks bundle run zerobus_publisher -t dev -p publix-workshop
# MAGIC ```
# MAGIC
# MAGIC The job runs with service-principal auth; secrets are injected from the `publix_workshop` scope.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Data Landed
# MAGIC
# MAGIC Run the checks below after the publisher job completes:

# COMMAND ----------

spark.sql("""
SELECT COUNT(*) as sales_events, COUNT(DISTINCT store_number) as stores
FROM publix_agentic_workshop.bronze.sales_events
""").display()

# COMMAND ----------

spark.sql("""
SELECT * FROM publix_agentic_workshop.bronze.sales_events LIMIT 5
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Key Concepts: Zerobus vs Kafka
# MAGIC
# MAGIC | Aspect | Kafka | Zerobus |
# MAGIC |--------|-------|---------|
# MAGIC | **Infrastructure** | You manage topics, brokers, replication | Databricks manages (serverless) |
# MAGIC | **Ingestion** | Consumer pulls from topic | Applications push to endpoint |
# MAGIC | **Latency** | Depends on consumer lag | Milliseconds, direct to Delta |
# MAGIC | **Governance** | Manual integration with UC | Native UC lineage, schema validation |
# MAGIC | **Scaling** | Manual partitions, consumer groups | Automatic, per endpoint |
# MAGIC | **Best for** | Multi-consumer, high-volume streams | Direct-to-Delta ingestion |
# MAGIC
# MAGIC **Zerobus is a serverless alternative to Kafka for pushing events straight into your lakehouse.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next: Notebook 4 - Medallion Pipeline
# MAGIC
# MAGIC Your bronze tables are now populated:
# MAGIC - `bronze.sales_events` - real-time sales from Zerobus publisher
# MAGIC - `bronze.price_updates` - real-time price changes from Zerobus
# MAGIC
# MAGIC **Next step:** Build the medallion pipeline (silver + gold) with Spark Declarative Pipelines.
# MAGIC Everyone in the workshop populates the same `medallion.gold_store_item_daily` table.
