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
# MAGIC ## Your Schema
# MAGIC
# MAGIC You all share one workspace and the shared `publix_technology` catalog.
# MAGIC Each participant builds in their OWN schema.
# MAGIC Run the next cell and type your first name in the `my_name` box that appears at the top.

# COMMAND ----------

dbutils.widgets.text("my_name", "", "Your first name (lowercase, no spaces)")
name = dbutils.widgets.get("my_name")
assert name and " " not in name, "Type your first name (lowercase, no spaces) in the my_name box at the top, then re-run."
CATALOG = "publix_technology"
SCHEMA = f"agentic_ai_training_{name}"
print(f"Your schema: {CATALOG}.{SCHEMA}")

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
# MAGIC - POS systems (POSA) and pricing systems (TPR) push events to the Zerobus endpoint
# MAGIC - Events are validated and written directly to `pos_sales_raw` (POSA) or `price_updates_raw` (TPR)
# MAGIC - No intermediate Kafka topics, no consumer lag
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Architecture Recap
# MAGIC
# MAGIC ```
# MAGIC Publix POS (POSA) / TPR Pricing
# MAGIC           |
# MAGIC           v (push via gRPC/REST)
# MAGIC    Zerobus Endpoint
# MAGIC           |
# MAGIC           v (writes with UC lineage)
# MAGIC    pos_sales_raw / price_updates_raw (Delta, Change Data Feed enabled)
# MAGIC           |
# MAGIC           v (Notebook 4: SDP explodes + decodes)
# MAGIC    silver_pos_sales (line items) / silver_tpr_prices (decoded prices)
# MAGIC           |
# MAGIC           v (aggregates)
# MAGIC    gold_store_item_daily (materialized view, queried by Genie)
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
# MAGIC > - Define two Zerobus streams (use the shared catalog publix_technology and YOUR schema agentic_ai_training_<yourname>):
# MAGIC >   1. publix_technology.agentic_ai_training_<yourname>.pos_sales_raw (POSA Kafka envelope with nested value.Basket.BasketItems array)
# MAGIC >   2. publix_technology.agentic_ai_training_<yourname>.price_updates_raw (TPR Kafka envelope with base64-encoded data fields)
# MAGIC > - For 60 seconds, publish synthetic events:
# MAGIC >   - 3-6 POSA sales per second (nested Basket with 1-8 items, store number, cashier, tenders)
# MAGIC >   - Occasional TPR price updates (10% chance per second, base64-encode Selling_Price and Effective_Date)
# MAGIC > - Use fire-and-forget ingestion (ingest_record_nowait)
# MAGIC > - Flush and close streams cleanly at the end
# MAGIC > - Use environment variables for all credentials (DATABRICKS_WORKSPACE_URL, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET, ZEROBUS_SERVER_ENDPOINT, DURATION_SECONDS, WORKSHOP_CATALOG env var for override)
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

Pumps synthetic Publix POSA sales + TPR price-update events into the bronze Delta tables
via the Zerobus Ingest SDK, so the real-time lab runs live without a Kafka topic.

Config comes from environment / job parameters (no secrets in code):
  ZEROBUS_SERVER_ENDPOINT   e.g. https://<workspace-id>.zerobus.eastus.azuredatabricks.net
  DATABRICKS_WORKSPACE_URL  e.g. https://adb-<id>.<n>.azuredatabricks.net
  DATABRICKS_CLIENT_ID      service principal application id (INSERT on the bronze tables)
  DATABRICKS_CLIENT_SECRET  service principal secret
  DURATION_SECONDS          how long to publish (default 60)

Install: pip install databricks-zerobus-ingest-sdk
"""

import base64
import json
import os
import random
import time
from datetime import datetime, timedelta
from uuid import uuid4

from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

CATALOG = "publix_technology"
SCHEMA = os.environ.get("WORKSHOP_SCHEMA", "agentic_ai_training_workshop")
SALES_TABLE = f"{CATALOG}.{SCHEMA}.pos_sales_raw"
PRICE_TABLE = f"{CATALOG}.{SCHEMA}.price_updates_raw"

SERVER_ENDPOINT = os.environ["ZEROBUS_SERVER_ENDPOINT"]
WORKSPACE_URL = os.environ["DATABRICKS_WORKSPACE_URL"]
CLIENT_ID = os.environ["DATABRICKS_CLIENT_ID"]
CLIENT_SECRET = os.environ["DATABRICKS_CLIENT_SECRET"]
DURATION_SECONDS = int(os.environ.get("DURATION_SECONDS", "60"))

STORE_NUMBERS = [100, 102, 104, 106, 108, 110, 112, 114]
PRODUCTS = [
    {"code": "0071230002519", "sku": 1001, "name": "Boar\\'s Head Deli Ham", "category": "Deli", "price": 6.99},
    {"code": "0041230001234", "sku": 1002, "name": "Publix Bakery Ciabatta", "category": "Bakery", "price": 2.49},
    {"code": "0041230004567", "sku": 1003, "name": "GreenWise Organic Milk", "category": "Dairy", "price": 4.29},
    {"code": "0078000073506", "sku": 1004, "name": "Coca-Cola 12-pack", "category": "Beverage", "price": 6.49},
    {"code": "0071230005678", "sku": 1005, "name": "Publix Hot Bar Sub", "category": "Deli", "price": 7.99},
    {"code": "0041230006789", "sku": 1006, "name": "Fresh Strawberries", "category": "Produce", "price": 3.99},
]

PRICE_TYPES = ["REGULAR", "DEAL", "CLEARANCE"]


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _encode_field(value: str) -> str:
    """Base64 encode a field (for TPR price fields)."""
    return base64.b64encode(value.encode()).decode()


def _generate_posa_event(now):
    """Generate a POSA sales event with nested Basket structure."""
    event_time = now - timedelta(seconds=random.randint(0, 3600))
    store_num = random.choice(STORE_NUMBERS)
    num_items = random.randint(1, 8)
    basket_items = []
    subtotal = 0.0
    for _ in range(num_items):
        prod = random.choice(PRODUCTS)
        qty = random.randint(1, 5)
        unit_price = round(prod["price"] * random.uniform(0.95, 1.10), 2)
        total_price = round(unit_price * qty, 2)
        subtotal += total_price
        basket_items.append({
            "Gtin": prod["code"], "Sku": prod["sku"], "Name": prod["name"],
            "FamilyGroup": prod["category"], "SubDepartmentId": 100 + random.randint(0, 5),
            "Quantity": qty, "UnitPrice": unit_price, "TotalPrice": total_price,
            "IsRefundItem": False, "IsMerchandise": True, "State": "ACTIVE",
        })
    tax_total = round(subtotal * 0.07, 2)
    savings = round(subtotal * random.uniform(0, 0.15), 2)
    basket = {
        "StoreNumber": store_num, "LaneNumber": random.randint(1, 6),
        "TransactionId": str(uuid4().hex[:16]),
        "StartTime": event_time.isoformat() + "Z",
        "EndTime": (event_time + timedelta(seconds=random.randint(30, 300))).isoformat() + "Z",
        "Subtotal": subtotal, "Total": round(subtotal + tax_total - savings, 2),
        "Savings": savings, "TaxTotal": tax_total, "BasketItems": basket_items,
        "BasketTenders": [{"Name": "VISA", "TenderType": "CARD",
            "ApprovedAmount": round(subtotal + tax_total, 2),
            "PaymentDetails": {"CardBrand": "Visa",
                "MaskedCardNumber": f"XXXX-XXXX-XXXX-{random.randint(1000, 9999)}", "EntryMethod": "CHIP"}}],
        "CashierDetails": [{"Username": f"cashier_{random.randint(1000, 9999)}", "Name": "Cashier", "DateOfBirth": "1990-01-01"}]
    }
    return {
        "partition": random.randint(0, 3), "offset": random.randint(100000, 999999),
        "timestamp": int(event_time.timestamp() * 1000), "timestampType": 0,
        "key": f"{store_num}:{event_time.strftime(\\'%Y%m%d\\')}",
        "value": {"Version": "1.0", "RequestId": str(uuid4()), "TicketNumber": f"TKT-{store_num}-{random.randint(100000, 999999)}",
            "Username": f"user_{random.randint(1000, 9999)}", "TransactionDateTime": event_time.isoformat() + "Z", "Basket": basket,
            "ReceiptText": f"Thank you for shopping at Publix Store #{store_num}!"}
    }


def _generate_tpr_event(now):
    """Generate a TPR price event with base64-encoded fields."""
    event_time = now - timedelta(hours=random.randint(0, 24))
    prod = random.choice(PRODUCTS)
    store_num = random.choice(STORE_NUMBERS)
    selling_price = round(prod["price"] * random.uniform(0.95, 1.15), 2)
    return {
        "key": f"{prod[\\'code\\']}:{store_num}",
        "data": {"SystemId": "TPR_PRICING", "EventType": "PRICE_UPDATE", "Event_Id": str(uuid4()),
            "Event_Timestamp": _encode_field(event_time.isoformat() + "Z"), "Item_Code": prod["code"],
            "Store_Number": store_num, "Price_Type": random.choice(PRICE_TYPES), "EventAction": "UPDATE",
            "Effective_Date": _encode_field(event_time.date().isoformat()),
            "Term_Date": _encode_field((event_time.date() + timedelta(days=30)).isoformat()),
            "Selling_Price": _encode_field(str(selling_price)), "Deal_Price": _encode_field(str(round(selling_price * 0.90, 2))),
            "Break_Retail_Price": _encode_field(str(round(selling_price * 1.05, 2))),
            "Sale_Quantity": random.randint(1, 100), "Deal_Quantity": random.randint(0, 50),
            "Mix_Match_Code": f"MM{random.randint(100, 999)}", "Vendor_Number": f"VND{random.randint(10000, 99999)}",
            "Created_By": f"user_{random.randint(1000, 9999)}", "Created_On": _encode_field(datetime.utcnow().isoformat() + "Z")},
        "topic": "publix.pricing.updates", "partition": random.randint(0, 2), "offset": random.randint(50000, 499999),
        "timestamp": int(event_time.timestamp() * 1000)
    }


def main() -> None:
    sdk = ZerobusSdk(SERVER_ENDPOINT, WORKSPACE_URL)
    options = StreamConfigurationOptions(record_type=RecordType.JSON)
    sales = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, TableProperties(SALES_TABLE), options)
    prices = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, TableProperties(PRICE_TABLE), options)
    print(f"[*] Publishing synthetic Publix events for {DURATION_SECONDS}s -> {SALES_TABLE}")
    start, count = time.time(), 0
    try:
        while time.time() - start < DURATION_SECONDS:
            now = datetime.utcnow()
            for _ in range(random.randint(3, 6)):
                event = _generate_posa_event(now)
                sales.ingest_record_nowait(event)
                count += 1
            if random.random() < 0.1:
                event = _generate_tpr_event(now)
                prices.ingest_record_nowait(event)
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

spark.sql(f"""
SELECT COUNT(*) as sales_events, COUNT(DISTINCT value.Basket.StoreNumber) as stores
FROM {CATALOG}.{SCHEMA}.pos_sales_raw
""").display()

# COMMAND ----------

spark.sql(f"""
SELECT value.Basket.StoreNumber, value.TicketNumber, value.TransactionDateTime, ARRAY_LENGTH(value.Basket.BasketItems) as num_items
FROM {CATALOG}.{SCHEMA}.pos_sales_raw LIMIT 5
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
# MAGIC Your bronze tables are now populated (in your own catalog):
# MAGIC - `pos_sales_raw` - real-time POSA sales events from Zerobus publisher (Kafka envelope with nested Basket)
# MAGIC - `price_updates_raw` - real-time TPR price events from Zerobus (Kafka envelope with base64-encoded fields)
# MAGIC
# MAGIC **Next step:** Build the medallion pipeline (silver + gold) with Spark Declarative Pipelines.
# MAGIC The silver layer will explode BasketItems and decode price fields, gold will aggregate daily sales.
