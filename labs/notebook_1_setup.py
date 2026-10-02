# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 1 - Setup & Mock Data Generation
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** Create the Unity Catalog, schemas, Volume, and bronze tables; populate with synthetic Kafka-shaped Publix sales and price data via Auto Loader.
# MAGIC Run this once, top to bottom. It is idempotent - safe to re-run.
# MAGIC
# MAGIC **Outcome:** Ready for Notebook 4 (SDP medallion) and Notebook 5+ (Genie/Apps).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 0 - Name your catalog (you all share this workspace)
# MAGIC
# MAGIC Everyone works in the **same workspace**, so each person builds in their **own catalog**.
# MAGIC Run the next cell, then type your first name in the `my_name` box that appears at the top.

# COMMAND ----------

dbutils.widgets.text("my_name", "", "Your first name (lowercase, no spaces)")
name = dbutils.widgets.get("my_name")
assert name and " " not in name, "Type your first name (lowercase, no spaces) in the my_name box at the top, then re-run."
CATALOG = f"publix_agentic_{name}"
print(f"Your catalog will be: {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 1 - Create Catalog, Schemas & Volume

# COMMAND ----------

# Your own catalog, namespaced by your name so it won't collide with anyone else's.
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f'CREATE SCHEMA IF NOT EXISTS {CATALOG}.bronze    COMMENT "Raw Auto Loader landing (JSON from Volume)"')
spark.sql(f'CREATE SCHEMA IF NOT EXISTS {CATALOG}.medallion COMMENT "Silver (streaming) + Gold (materialized)"')

# Create a Volume for landing Kafka-envelope JSON files
VOLUME_NAME = f"{CATALOG}.bronze.kafka_landing"
spark.sql(f"CREATE VOLUME IF NOT EXISTS {VOLUME_NAME}")
VOLUME_PATH = f"/Volumes/{VOLUME_NAME}"
print(f"Volume path: {VOLUME_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 2 - Create Bronze Auto Loader Tables (Raw Kafka Envelopes)
# MAGIC
# MAGIC These tables will be populated by Auto Loader reading JSON from the Volume.
# MAGIC Silver transformations will parse the Kafka envelopes and extract nested data.

# COMMAND ----------

# POSA Sales events (raw Kafka envelope structure).
# Auto Loader will ingest JSON files from the sales/ subdirectory.
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.bronze.pos_sales_raw (
  partition INT,
  offset BIGINT,
  timestamp BIGINT,
  timestampType INT,
  key STRING,
  value STRUCT<
    Version STRING,
    RequestId STRING,
    TicketNumber STRING,
    Username STRING,
    TransactionDateTime STRING,
    Basket STRUCT<
      StoreNumber INT,
      LaneNumber INT,
      TransactionId STRING,
      StartTime STRING,
      EndTime STRING,
      Subtotal DOUBLE,
      Total DOUBLE,
      Savings DOUBLE,
      TaxTotal DOUBLE,
      BasketItems ARRAY<STRUCT<
        Gtin STRING,
        Sku INT,
        Name STRING,
        FamilyGroup STRING,
        SubDepartmentId INT,
        Quantity INT,
        UnitPrice DOUBLE,
        TotalPrice DOUBLE,
        IsRefundItem BOOLEAN,
        IsMerchandise BOOLEAN,
        State STRING
      >>,
      BasketTenders ARRAY<STRUCT<
        Name STRING,
        TenderType STRING,
        ApprovedAmount DOUBLE,
        PaymentDetails STRUCT<
          CardBrand STRING,
          MaskedCardNumber STRING,
          EntryMethod STRING
        >
      >>,
      CashierDetails ARRAY<STRUCT<
        Username STRING,
        Name STRING,
        DateOfBirth STRING
      >>
    >,
    ReceiptText STRING
  >,
  _rescued_data STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")

# COMMAND ----------

# TPR Price updates (raw Kafka envelope structure with base64-encoded fields).
# Auto Loader will ingest JSON files from the prices/ subdirectory.
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.bronze.price_updates_raw (
  key STRING,
  data STRUCT<
    SystemId STRING,
    EventType STRING,
    Event_Id STRING,
    Event_Timestamp STRING,
    Item_Code STRING,
    Store_Number INT,
    Price_Type STRING,
    EventAction STRING,
    Effective_Date STRING,
    Term_Date STRING,
    Selling_Price STRING,
    Deal_Price STRING,
    Break_Retail_Price STRING,
    Sale_Quantity INT,
    Deal_Quantity INT,
    Mix_Match_Code STRING,
    Vendor_Number STRING,
    Created_By STRING,
    Created_On STRING
  >,
  topic STRING,
  partition INT,
  offset BIGINT,
  timestamp BIGINT,
  _rescued_data STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 3 - Generate Synthetic Kafka-Shaped Data & Populate Bronze
# MAGIC
# MAGIC We generate realistic Publix POSA sales and TPR price events in Kafka-envelope format.
# MAGIC Events are written as JSON files to the Volume, then Auto Loader ingests them.

# COMMAND ----------

import json
import base64
from datetime import datetime, timedelta
from uuid import uuid4
import random

CATALOG = f"publix_agentic_{dbutils.widgets.get('my_name')}"
VOLUME_PATH = f"/Volumes/{CATALOG}.bronze.kafka_landing"

# Product catalog and store numbers (same as src/setup/publix_data_gen.py)
PRODUCTS = [
    {"code": "0071230002519", "sku": 1001, "name": "Boar's Head Deli Ham", "category": "Deli", "base_price": 6.99},
    {"code": "0041230001234", "sku": 1002, "name": "Publix Bakery Ciabatta", "category": "Bakery", "base_price": 2.49},
    {"code": "0041230004567", "sku": 1003, "name": "GreenWise Organic Milk", "category": "Dairy", "base_price": 4.29},
    {"code": "0078000073506", "sku": 1004, "name": "Coca-Cola 12-pack", "category": "Beverage", "base_price": 6.49},
    {"code": "0071230005678", "sku": 1005, "name": "Publix Hot Bar Sub", "category": "Deli", "base_price": 7.99},
    {"code": "0041230002111", "sku": 1006, "name": "Fresh Strawberries", "category": "Produce", "base_price": 3.99},
    {"code": "0041230008765", "sku": 1007, "name": "Publix Premium Coffee", "category": "Grocery", "base_price": 8.49},
    {"code": "0041230009876", "sku": 1008, "name": "Fresh Broccoli", "category": "Produce", "base_price": 2.99},
    {"code": "0041230003322", "sku": 1009, "name": "Kerrygold Irish Butter", "category": "Dairy", "base_price": 5.99},
    {"code": "0078000055555", "sku": 1010, "name": "Tropicana Orange Juice", "category": "Beverage", "base_price": 3.49},
]

STORE_NUMBERS = [100, 102, 104, 106, 108, 110, 112, 114]
PRICE_TYPES = ["REGULAR", "DEAL", "CLEARANCE"]

# Helper functions
def mask_card(card_num: str) -> str:
    return f"XXXX-XXXX-XXXX-{card_num[-4:]}"

def encode_field(value: str) -> str:
    """Base64 encode a field (for TPR price fields)."""
    return base64.b64encode(value.encode()).decode()

def generate_posa_event(now):
    """Generate a POSA sales event."""
    event_time = now - timedelta(seconds=random.randint(0, 3600))
    store_num = random.choice(STORE_NUMBERS)

    num_items = random.randint(1, 8)
    basket_items = []
    subtotal = 0.0

    for _ in range(num_items):
        prod = random.choice(PRODUCTS)
        qty = random.randint(1, 5)
        unit_price = round(prod["base_price"] * random.uniform(0.95, 1.10), 2)
        total_price = round(unit_price * qty, 2)
        subtotal += total_price
        basket_items.append({
            "Gtin": prod["code"],
            "Sku": prod["sku"],
            "Name": prod["name"],
            "FamilyGroup": prod["category"],
            "SubDepartmentId": 100 + random.randint(0, 5),
            "Quantity": qty,
            "UnitPrice": unit_price,
            "TotalPrice": total_price,
            "IsRefundItem": False,
            "IsMerchandise": True,
            "State": "ACTIVE",
        })

    tax_total = round(subtotal * 0.07, 2)
    savings = round(subtotal * random.uniform(0, 0.15), 2)

    basket = {
        "StoreNumber": store_num,
        "LaneNumber": random.randint(1, 6),
        "TransactionId": str(uuid4().hex[:16]),
        "StartTime": event_time.isoformat() + "Z",
        "EndTime": (event_time + timedelta(seconds=random.randint(30, 300))).isoformat() + "Z",
        "Subtotal": subtotal,
        "Total": round(subtotal + tax_total - savings, 2),
        "Savings": savings,
        "TaxTotal": tax_total,
        "BasketItems": basket_items,
        "BasketTenders": [{
            "Name": "VISA",
            "TenderType": "CARD",
            "ApprovedAmount": round(subtotal + tax_total, 2),
            "PaymentDetails": {
                "CardBrand": "Visa",
                "MaskedCardNumber": mask_card("".join(random.choices("0123456789", k=16))),
                "EntryMethod": "CHIP"
            }
        }],
        "CashierDetails": [{
            "Username": f"cashier_{random.randint(1000, 9999)}",
            "Name": "Cashier",
            "DateOfBirth": "1990-01-01"
        }]
    }

    return {
        "partition": random.randint(0, 3),
        "offset": random.randint(100000, 999999),
        "timestamp": int(event_time.timestamp() * 1000),
        "timestampType": 0,
        "key": f"{store_num}:{event_time.strftime('%Y%m%d')}",
        "value": {
            "Version": "1.0",
            "RequestId": str(uuid4()),
            "TicketNumber": f"TKT-{store_num}-{random.randint(100000, 999999)}",
            "Username": f"user_{random.randint(1000, 9999)}",
            "TransactionDateTime": event_time.isoformat() + "Z",
            "Basket": basket,
            "ReceiptText": f"Thank you for shopping at Publix Store #{store_num}!"
        }
    }

def generate_tpr_event(now):
    """Generate a TPR price event."""
    event_time = now - timedelta(hours=random.randint(0, 24))
    prod = random.choice(PRODUCTS)
    store_num = random.choice(STORE_NUMBERS)

    selling_price = round(prod["base_price"] * random.uniform(0.95, 1.15), 2)

    return {
        "key": f"{prod['code']}:{store_num}",
        "data": {
            "SystemId": "TPR_PRICING",
            "EventType": "PRICE_UPDATE",
            "Event_Id": str(uuid4()),
            "Event_Timestamp": encode_field(event_time.isoformat() + "Z"),
            "Item_Code": prod["code"],
            "Store_Number": store_num,
            "Price_Type": random.choice(PRICE_TYPES),
            "EventAction": "UPDATE",
            "Effective_Date": encode_field(event_time.date().isoformat()),
            "Term_Date": encode_field((event_time.date() + timedelta(days=30)).isoformat()),
            "Selling_Price": encode_field(str(selling_price)),
            "Deal_Price": encode_field(str(round(selling_price * 0.90, 2))),
            "Break_Retail_Price": encode_field(str(round(selling_price * 1.05, 2))),
            "Sale_Quantity": random.randint(1, 100),
            "Deal_Quantity": random.randint(0, 50),
            "Mix_Match_Code": f"MM{random.randint(100, 999)}",
            "Vendor_Number": f"VND{random.randint(10000, 99999)}",
            "Created_By": f"user_{random.randint(1000, 9999)}",
            "Created_On": encode_field(datetime.utcnow().isoformat() + "Z")
        },
        "topic": "publix.pricing.updates",
        "partition": random.randint(0, 2),
        "offset": random.randint(50000, 499999),
        "timestamp": int(event_time.timestamp() * 1000)
    }

# Generate and write events to Volume
import os
now = datetime.utcnow()

sales_dir = f"{VOLUME_PATH}/sales"
prices_dir = f"{VOLUME_PATH}/prices"

dbutils.fs.mkdirs(sales_dir)
dbutils.fs.mkdirs(prices_dir)

num_sales = 100
num_prices = 20

for i in range(num_sales):
    event = generate_posa_event(now)
    filename = f"sales_{now.isoformat().replace(':', '-')}_{uuid4().hex[:8]}.json"
    dbutils.fs.put(f"{sales_dir}/{filename}", json.dumps(event), overwrite=True)

for i in range(num_prices):
    event = generate_tpr_event(now)
    filename = f"price_{now.isoformat().replace(':', '-')}_{uuid4().hex[:8]}.json"
    dbutils.fs.put(f"{prices_dir}/{filename}", json.dumps(event), overwrite=True)

print(f"Generated {num_sales} sales events and {num_prices} price events to {VOLUME_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 3b - Auto Loader Setup
# MAGIC
# MAGIC Configure Auto Loader to stream JSON files from the Volume into the bronze tables.

# COMMAND ----------

from pyspark.sql.functions import input_file_name, current_timestamp

CATALOG = f"publix_agentic_{dbutils.widgets.get('my_name')}"

# Load POSA sales events via Auto Loader
sales_path = f"/Volumes/{CATALOG}.bronze.kafka_landing/sales"
df_sales = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", f"{VOLUME_PATH}/.schema/sales")
    .option("cloudFiles.inferColumnTypes", "true")
    .load(sales_path)
    .writeStream
    .format("delta")
    .mode("append")
    .option("checkpointLocation", f"{VOLUME_PATH}/.checkpoint/sales")
    .table(f"{CATALOG}.bronze.pos_sales_raw"))

print(f"Auto Loader configured for {sales_path}")

# Load TPR price events via Auto Loader
prices_path = f"/Volumes/{CATALOG}.bronze.kafka_landing/prices"
df_prices = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", f"{VOLUME_PATH}/.schema/prices")
    .option("cloudFiles.inferColumnTypes", "true")
    .load(prices_path)
    .writeStream
    .format("delta")
    .mode("append")
    .option("checkpointLocation", f"{VOLUME_PATH}/.checkpoint/prices")
    .table(f"{CATALOG}.bronze.price_updates_raw"))

print(f"Auto Loader configured for {prices_path}")

import time
time.sleep(5)  # Wait for streams to start

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 4 - (Optional) Grant the Zerobus Publisher Service Principal
# MAGIC
# MAGIC If you are running the optional Zerobus publisher (Notebook 3), the shared workshop
# MAGIC service principal needs INSERT access to the bronze raw tables. Your workshop admin
# MAGIC creates the SP once (see `SETUP_SERVICE_PRINCIPAL.md`) and gives you its application ID.
# MAGIC
# MAGIC **Skip this if you are not doing the Zerobus lab** (Auto Loader is enough for the rest).

# COMMAND ----------

CATALOG = f"publix_agentic_{dbutils.widgets.get('my_name')}"
ZEROBUS_SP = "<zerobus-sp-application-id>"   # e.g. "1b103dc1-cf0a-42ae-94ba-253f9ed2059d"

if ZEROBUS_SP and not ZEROBUS_SP.startswith("<"):
    spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{ZEROBUS_SP}`")
    spark.sql(f"GRANT USE SCHEMA  ON SCHEMA  {CATALOG}.bronze TO `{ZEROBUS_SP}`")
    spark.sql(f"GRANT INSERT ON TABLE {CATALOG}.bronze.pos_sales_raw TO `{ZEROBUS_SP}`")
    spark.sql(f"GRANT INSERT ON TABLE {CATALOG}.bronze.price_updates_raw TO `{ZEROBUS_SP}`")
    print(f"Granted permissions to {ZEROBUS_SP}")
else:
    print("ZEROBUS_SP not configured - skipping. Optional if using Zerobus in Notebook 3.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 5 - Verify Auto Loader Setup

# COMMAND ----------

CATALOG = f"publix_agentic_{dbutils.widgets.get('my_name')}"

# Check bronze tables
print("=== Bronze Tables (Auto Loader from Volume) ===")
sales_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {CATALOG}.bronze.pos_sales_raw").collect()[0]["cnt"]
prices_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {CATALOG}.bronze.price_updates_raw").collect()[0]["cnt"]

print(f"POSA Sales events: {sales_count}")
print(f"TPR Price events: {prices_count}")

print("\nPOSA Sales schema (raw Kafka envelope):")
spark.sql(f"DESC {CATALOG}.bronze.pos_sales_raw").display()

print("\nTPR Prices schema (raw Kafka envelope):")
spark.sql(f"DESC {CATALOG}.bronze.price_updates_raw").display()

print("\nSample POSA sales event:")
spark.sql(f"SELECT value.Basket.StoreNumber, value.TicketNumber, value.TransactionDateTime FROM {CATALOG}.bronze.pos_sales_raw LIMIT 1").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup Complete!
# MAGIC
# MAGIC You now have (in **your own** catalog):
# MAGIC - Catalog: `publix_agentic_<yourname>`
# MAGIC - Volume: `/Volumes/{catalog}.bronze.kafka_landing/` with `sales/` and `prices/` subdirectories
# MAGIC - Schemas: `bronze` (Auto Loader landing), `medallion` (silver + gold)
# MAGIC - Tables:
# MAGIC   - `bronze.pos_sales_raw` - POSA sales events (Kafka envelope with nested Basket)
# MAGIC   - `bronze.price_updates_raw` - TPR price events (Kafka envelope with base64-encoded fields)
# MAGIC - Auto Loader streams ingesting JSON from the Volume in real-time
# MAGIC
# MAGIC **Next steps:**
# MAGIC - **Notebook 4** - Build the medallion pipeline:
# MAGIC   - **Silver layer** parses the nested Kafka envelopes, explodes `BasketItems[]` to line items, base64-decodes TPR fields
# MAGIC   - **Gold layer** aggregates to daily store-item performance
# MAGIC - **Notebook 5** - Create a Genie space to query the gold layer
# MAGIC - **Notebook 6** - Build a Databricks App on top
