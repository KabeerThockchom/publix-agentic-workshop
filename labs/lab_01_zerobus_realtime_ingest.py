# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 1 - Real-time Ingest with Zerobus
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** Ingest live Publix sales and price-update events into Delta tables using Zerobus, without any message-bus ops. ~20 minutes.
# MAGIC
# MAGIC Zerobus is a push API that writes data straight to governed Delta tables. Today you will:
# MAGIC 1. Build a synthetic event publisher (what a real Kafka producer would do)
# MAGIC 2. Push sales and price-update events into the bronze layer in real time
# MAGIC 3. Validate the ingestion and count the rows
# MAGIC
# MAGIC Then tomorrow, your medallion pipeline will read from this bronze table and build your data estate.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What is Zerobus? (And why it matters to Publix)
# MAGIC
# MAGIC **Zerobus** is part of Databricks Lakeflow Connect - a serverless push API that takes events directly to
# MAGIC Delta tables. No Kafka cluster to run, no topic management, no separate message bus.
# MAGIC
# MAGIC ### For Publix, the pitch:
# MAGIC - **Write-only Kafka-compatible API (Beta)**: Kafka producers can point at Zerobus instead of Kafka with
# MAGIC   zero code change. Events land in governed Delta tables, not stranded in a topic.
# MAGIC - **No infrastructure ops**: Databricks runs the endpoint. You get schema validation + UC lineage for free.
# MAGIC - **Direct to the warehouse**: Events ingest at milliseconds latency, straight into bronze tables. No
# MAGIC   ETL shuffle, no batch window - real time.
# MAGIC - **Lower cost**: You pay DBUs, not Kafka cluster fees + topic replication.
# MAGIC
# MAGIC ### Trade-off (honest):
# MAGIC Zerobus write-only APIs mean you can't run Kafka consumers off it. If Publix needs true pub/sub
# MAGIC (many independent consumers of the same topic), stick with Kafka. If you just want events to warehouse,
# MAGIC Zerobus is simpler and cheaper.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prereqs: Service Principal + Secret Scope
# MAGIC
# MAGIC Before we write any code, confirm these are set up (they should be):
# MAGIC
# MAGIC | Item | Status |
# MAGIC |------|--------|
# MAGIC | **Service Principal** | App ID `<service-principal-app-id>` (INSERT on bronze tables) |
# MAGIC | **Secret Scope** | `publix_workshop` contains `zerobus_client_id` and `zerobus_client_secret` |
# MAGIC | **Zerobus Endpoint** | `https://<workspace-id>.zerobus.eastus.azuredatabricks.net` |
# MAGIC | **SDK** | `pip install databricks-zerobus-ingest-sdk` (already installed in your cluster) |
# MAGIC
# MAGIC Confirm the secrets are readable:

# COMMAND ----------

try:
    client_id = dbutils.secrets.get("publix_workshop", "zerobus_client_id")
    client_secret = dbutils.secrets.get("publix_workshop", "zerobus_client_secret")
    print(f"[✓] Secrets found. Client ID: {client_id[:20]}...")
except Exception as e:
    print(f"[✗] Secret error: {e}. Ask the instructor to set up the scope.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Your First Genie Code Prompt: Synthetic Sales Publisher
# MAGIC
# MAGIC Instead of connecting to a live Kafka topic (which we might not have during the lab), we will
# MAGIC build a **synthetic publisher** in Python that simulates Publix sales events flowing in real time.
# MAGIC
# MAGIC This is what a real Kafka producer would do - the only difference is we're generating mock data instead
# MAGIC of reading from a POS system.
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Write a Python script that:
# MAGIC > 1. Reads Zerobus credentials from the publix_workshop secret scope (zerobus_client_id, zerobus_client_secret)
# MAGIC > 2. Uses the Zerobus SDK (ZerobusSdk from zerobus.sdk.sync) to create a stream to publix_agentic_workshop.bronze.sales_events
# MAGIC > 3. Generates synthetic Publix sales events (event_id, store_number, event_timestamp, item_id, item_name, item_category, quantity_sold, unit_price, total_amount, cashier_id, transaction_id, ingestion_time) with realistic product/store/quantity data
# MAGIC > 4. Pumps events into the table via ingest_record_nowait() for ~30 seconds, emitting 3-5 events per second
# MAGIC > 5. Flushes the stream and prints a summary (total events pushed)
# MAGIC >
# MAGIC > Use this endpoint and workspace URL:
# MAGIC > - Endpoint: https://<workspace-id>.zerobus.eastus.azuredatabricks.net
# MAGIC > - Workspace: https://adb-<workspace-id>.17.azuredatabricks.net
# MAGIC > - Schema: RecordType.JSON, StreamConfigurationOptions, TableProperties as in the SDK
# MAGIC > ```
# MAGIC
# MAGIC Open Genie Code and try the prompt above. It should build a publisher that runs for 30s and prints
# MAGIC how many sales events it pushed. If you get an error, ask Genie Code to debug it.

# COMMAND ----------

# reference solution: synthetic sales publisher
import os
import random
import time
from datetime import datetime
from uuid import uuid4

from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

# Config
WORKSPACE_URL = "https://adb-<workspace-id>.17.azuredatabricks.net"
ZEROBUS_ENDPOINT = "https://<workspace-id>.zerobus.eastus.azuredatabricks.net"
SALES_TABLE = "publix_agentic_workshop.bronze.sales_events"
DURATION_SEC = 30

# Read credentials from secret scope
client_id = dbutils.secrets.get("publix_workshop", "zerobus_client_id")
client_secret = dbutils.secrets.get("publix_workshop", "zerobus_client_secret")

# Publix product catalog (realistic mix)
PRODUCTS = [
    {"id": 1001, "name": "Boar's Head Deli Ham", "category": "Deli", "price": 6.99},
    {"id": 1002, "name": "Publix Bakery Bread", "category": "Bakery", "price": 2.49},
    {"id": 1003, "name": "GreenWise Organic Milk", "category": "Dairy", "price": 4.29},
    {"id": 1004, "name": "Coca-Cola 12-pack", "category": "Beverage", "price": 6.49},
    {"id": 1005, "name": "Publix Deli Sub", "category": "Deli", "price": 7.99},
    {"id": 1006, "name": "Fresh Strawberries", "category": "Produce", "price": 3.99},
]
STORE_NUMBERS = [100, 102, 104, 106, 108, 110, 112, 114]

# Initialize Zerobus SDK
sdk = ZerobusSdk(ZEROBUS_ENDPOINT, WORKSPACE_URL)
options = StreamConfigurationOptions(record_type=RecordType.JSON)
stream = sdk.create_stream(client_id, client_secret, TableProperties(SALES_TABLE), options)

def iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"

try:
    print(f"[*] Publishing synthetic Publix sales for {DURATION_SEC}s -> {SALES_TABLE}")
    start_time = time.time()
    event_count = 0

    while time.time() - start_time < DURATION_SEC:
        now = iso_now()

        # Generate 3-5 sales events per second
        num_events = random.randint(3, 5)
        for _ in range(num_events):
            product = random.choice(PRODUCTS)
            qty = random.randint(1, 10)

            sales_event = {
                "event_id": str(uuid4()),
                "store_number": random.choice(STORE_NUMBERS),
                "event_timestamp": now,
                "item_id": product["id"],
                "item_name": product["name"],
                "item_category": product["category"],
                "quantity_sold": qty,
                "unit_price": float(product["price"]),
                "total_amount": round(float(product["price"]) * qty, 2),
                "cashier_id": f"C{random.randint(1000, 9999)}",
                "transaction_id": f"TX{uuid4().hex[:12]}",
                "ingestion_time": now,
            }
            stream.ingest_record_nowait(sales_event)
            event_count += 1

        time.sleep(1)  # One batch per second

    # Flush all pending records
    stream.flush()
    print(f"[OK] Published {event_count} sales events in {DURATION_SEC}s")

finally:
    stream.close()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extend Your Publisher: Add Price-Update Events
# MAGIC
# MAGIC Good event systems emit more than just transactions. Prices change, promotions run, inventory swings.
# MAGIC Extend your publisher to also push occasional price-update events to the `price_updates` table.
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Extend the sales publisher above to also ingest price-update events. While publishing sales events,
# MAGIC > occasionally (about 10% of the time per cycle) emit a price-update event where a random product's price
# MAGIC > changes by +/- 5%.
# MAGIC >
# MAGIC > New table: publix_agentic_workshop.bronze.price_updates
# MAGIC > New event schema: event_id, event_timestamp, item_id, item_name, old_price, new_price, effective_date, ingestion_time
# MAGIC >
# MAGIC > Use two parallel Zerobus streams (one for sales, one for prices) or reuse the same SDK with two tables.
# MAGIC > Use ingest_record_nowait() for fire-and-forget throughput.
# MAGIC > ```

# COMMAND ----------

# reference solution: publisher with both sales and price events
import os
import random
import time
from datetime import datetime
from uuid import uuid4

from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

# Config
WORKSPACE_URL = "https://adb-<workspace-id>.17.azuredatabricks.net"
ZEROBUS_ENDPOINT = "https://<workspace-id>.zerobus.eastus.azuredatabricks.net"
SALES_TABLE = "publix_agentic_workshop.bronze.sales_events"
PRICE_TABLE = "publix_agentic_workshop.bronze.price_updates"
DURATION_SEC = 30

# Read credentials from secret scope
client_id = dbutils.secrets.get("publix_workshop", "zerobus_client_id")
client_secret = dbutils.secrets.get("publix_workshop", "zerobus_client_secret")

# Publix catalog
PRODUCTS = [
    {"id": 1001, "name": "Boar's Head Deli Ham", "category": "Deli", "price": 6.99},
    {"id": 1002, "name": "Publix Bakery Bread", "category": "Bakery", "price": 2.49},
    {"id": 1003, "name": "GreenWise Organic Milk", "category": "Dairy", "price": 4.29},
    {"id": 1004, "name": "Coca-Cola 12-pack", "category": "Beverage", "price": 6.49},
    {"id": 1005, "name": "Publix Deli Sub", "category": "Deli", "price": 7.99},
    {"id": 1006, "name": "Fresh Strawberries", "category": "Produce", "price": 3.99},
]
STORE_NUMBERS = [100, 102, 104, 106, 108, 110, 112, 114]

# Initialize two Zerobus streams
sdk = ZerobusSdk(ZEROBUS_ENDPOINT, WORKSPACE_URL)
options = StreamConfigurationOptions(record_type=RecordType.JSON)

stream_sales = sdk.create_stream(client_id, client_secret, TableProperties(SALES_TABLE), options)
stream_prices = sdk.create_stream(client_id, client_secret, TableProperties(PRICE_TABLE), options)

def iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"

try:
    print(f"[*] Publishing Publix events (sales + prices) for {DURATION_SEC}s")
    start_time = time.time()
    sales_count = 0
    price_count = 0

    while time.time() - start_time < DURATION_SEC:
        now = iso_now()

        # Sales events
        num_events = random.randint(3, 5)
        for _ in range(num_events):
            product = random.choice(PRODUCTS)
            qty = random.randint(1, 10)

            sales_event = {
                "event_id": str(uuid4()),
                "store_number": random.choice(STORE_NUMBERS),
                "event_timestamp": now,
                "item_id": product["id"],
                "item_name": product["name"],
                "item_category": product["category"],
                "quantity_sold": qty,
                "unit_price": float(product["price"]),
                "total_amount": round(float(product["price"]) * qty, 2),
                "cashier_id": f"C{random.randint(1000, 9999)}",
                "transaction_id": f"TX{uuid4().hex[:12]}",
                "ingestion_time": now,
            }
            stream_sales.ingest_record_nowait(sales_event)
            sales_count += 1

        # Occasional price updates (10% chance)
        if random.random() < 0.1:
            product = random.choice(PRODUCTS)
            old_price = float(product["price"])
            new_price = round(old_price * random.uniform(0.95, 1.05), 2)

            price_event = {
                "event_id": str(uuid4()),
                "event_timestamp": now,
                "item_id": product["id"],
                "item_name": product["name"],
                "old_price": old_price,
                "new_price": new_price,
                "effective_date": datetime.utcnow().date().isoformat(),
                "ingestion_time": now,
            }
            stream_prices.ingest_record_nowait(price_event)
            price_count += 1

        time.sleep(1)

    # Flush
    stream_sales.flush()
    stream_prices.flush()

    print(f"[OK] Published {sales_count} sales + {price_count} price events")

finally:
    stream_sales.close()
    stream_prices.close()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validate: Count the Rows
# MAGIC
# MAGIC Let's confirm your data landed in the bronze tables. Run the cell below to see:
# MAGIC - Total row count in `sales_events`
# MAGIC - 5 sample sales rows
# MAGIC - Total row count in `price_updates`

# COMMAND ----------

# Count and sample the ingested data
sales_count = spark.sql("""
    SELECT COUNT(*) as total_rows FROM publix_agentic_workshop.bronze.sales_events
""").collect()[0]["total_rows"]

print(f"Total sales events ingested: {sales_count}")
print("\nRecent sales (sample):")
spark.sql("""
    SELECT event_id, store_number, item_name, quantity_sold, total_amount, event_timestamp
    FROM publix_agentic_workshop.bronze.sales_events
    ORDER BY ingestion_time DESC
    LIMIT 5
""").display()

price_count = spark.sql("""
    SELECT COUNT(*) as total_rows FROM publix_agentic_workshop.bronze.price_updates
""").collect()[0]["total_rows"]

print(f"\nTotal price updates ingested: {price_count}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why This Matters (And What Happens Next)
# MAGIC
# MAGIC You just ingested real-time events directly into a governed Delta table - no Kafka cluster, no
# MAGIC topic to manage, no shuffle ETL. That's the unlock: **events go straight from your systems into the warehouse**.
# MAGIC
# MAGIC ### In a real Publix deployment:
# MAGIC - POS systems (or your app) emit events via gRPC or REST to the Zerobus endpoint
# MAGIC - Events land in `publix_agentic_workshop.bronze.sales_events` with schema validation
# MAGIC - Unity Catalog knows who read/wrote what (lineage + governance for free)
# MAGIC - Your medallion pipeline reads this bronze table and transforms it into silver + gold layers
# MAGIC
# MAGIC ### Today's simulation:
# MAGIC This synthetic publisher stands in for your Kafka topic. In a real workshop, we would point a
# MAGIC live Kafka producer at the Zerobus Kafka-compatible endpoint (Beta) instead.
# MAGIC
# MAGIC ### Your next step:
# MAGIC **Lab 2** will transform this raw bronze table into a clean, deduplicated, fact+dimension silver layer
# MAGIC using Spark Declarative Pipelines. The pipeline you build will run nightly and feed Lab 3
# MAGIC (your Genie space).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC - **What you built**: A Python publisher that pushes Publix sales and price events via Zerobus SDK
# MAGIC   into Delta tables, fire-and-forget (high throughput, no acks overhead).
# MAGIC - **What Zerobus gives you**: Serverless ingestion, direct to UC tables, schema validation, zero
# MAGIC   message-bus ops.
# MAGIC - **What's next**: Lab 2 - medallion transformation pipeline on this bronze data.
# MAGIC
# MAGIC Ready? Move on to **Lab 2 - Medallion Pipeline with Spark Declarative Pipelines**.
