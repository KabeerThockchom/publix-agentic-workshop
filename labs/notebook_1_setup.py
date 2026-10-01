# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 1 - Setup & Mock Data Generation
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** Create the Unity Catalog, schemas, and bronze tables; populate with synthetic Publix sales and price data.
# MAGIC Run this once, top to bottom. It is idempotent - safe to re-run.
# MAGIC
# MAGIC **Outcome:** Ready for Notebook 2 (Kafka producer) or Notebook 3 (Zerobus ingest).

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
# MAGIC ## Part 1 - Create Catalog & Schemas

# COMMAND ----------

# Your own catalog, namespaced by your name so it won't collide with anyone else's.
# Uses the CATALOG variable (built from the my_name widget above) - no deprecated ${...} SQL substitution.
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f'CREATE SCHEMA IF NOT EXISTS {CATALOG}.bronze    COMMENT "Raw ingest landing tables"')
spark.sql(f'CREATE SCHEMA IF NOT EXISTS {CATALOG}.medallion COMMENT "Silver (streaming) + Gold (materialized)"')

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 2 - Create Bronze Landing Tables

# COMMAND ----------

# Sales events (target for Kafka producer or Zerobus). Timestamps land as ISO strings; cast in silver.
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.bronze.sales_events (
  event_id        STRING,
  store_number    INT,
  event_timestamp STRING,
  item_id         INT,
  item_name       STRING,
  item_category   STRING,
  quantity_sold   INT,
  unit_price      DOUBLE,
  total_amount    DOUBLE,
  cashier_id      STRING,
  transaction_id  STRING,
  ingestion_time  STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")

# COMMAND ----------

# Item price updates (target for Kafka producer or Zerobus).
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.bronze.price_updates (
  event_id        STRING,
  event_timestamp STRING,
  item_id         INT,
  item_name       STRING,
  old_price       DOUBLE,
  new_price       DOUBLE,
  effective_date  STRING,
  ingestion_time  STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 3 - Generate & Insert Mock Data
# MAGIC
# MAGIC We will populate both tables with synthetic Publix sales and price events so you can proceed
# MAGIC through Notebooks 2 and 3 even without external Kafka or Zerobus configured.

# COMMAND ----------

import random
from datetime import datetime, timedelta
from uuid import uuid4
import json

# Configuration - reads your name from the widget set in Part 0
CATALOG = f"publix_agentic_{dbutils.widgets.get('my_name')}"
SALES_TABLE = f"{CATALOG}.bronze.sales_events"
PRICE_TABLE = f"{CATALOG}.bronze.price_updates"

STORE_NUMBERS = [100, 102, 104, 106, 108, 110, 112, 114]
PRODUCTS = [
    {"id": 1001, "name": "Boar's Head Deli Ham", "category": "Deli", "price": 6.99},
    {"id": 1002, "name": "Publix Bakery Bread", "category": "Bakery", "price": 2.49},
    {"id": 1003, "name": "GreenWise Organic Milk", "category": "Dairy", "price": 4.29},
    {"id": 1004, "name": "Coca-Cola 12-pack", "category": "Beverage", "price": 6.49},
    {"id": 1005, "name": "Publix Deli Sub", "category": "Deli", "price": 7.99},
    {"id": 1006, "name": "Fresh Strawberries", "category": "Produce", "price": 3.99},
]

def iso_now():
    """Return current time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"

def generate_sales_events(num_events=50):
    """Generate synthetic sales events."""
    events = []
    now = datetime.utcnow()
    for _ in range(num_events):
        p = random.choice(PRODUCTS)
        qty = random.randint(1, 10)
        ts = now - timedelta(hours=random.randint(0, 24))
        events.append({
            "event_id": str(uuid4()),
            "store_number": random.choice(STORE_NUMBERS),
            "event_timestamp": ts.isoformat() + "Z",
            "item_id": p["id"],
            "item_name": p["name"],
            "item_category": p["category"],
            "quantity_sold": qty,
            "unit_price": float(p["price"]),
            "total_amount": round(p["price"] * qty, 2),
            "cashier_id": f"C{random.randint(1000, 9999)}",
            "transaction_id": f"TX{uuid4().hex[:12]}",
            "ingestion_time": iso_now(),
        })
    return events

def generate_price_events(num_events=5):
    """Generate synthetic price update events."""
    events = []
    now = datetime.utcnow()
    for _ in range(num_events):
        p = random.choice(PRODUCTS)
        ts = now - timedelta(hours=random.randint(0, 48))
        new_price = round(p["price"] * random.uniform(0.95, 1.05), 2)
        events.append({
            "event_id": str(uuid4()),
            "event_timestamp": ts.isoformat() + "Z",
            "item_id": p["id"],
            "item_name": p["name"],
            "old_price": float(p["price"]),
            "new_price": new_price,
            "effective_date": ts.date().isoformat(),
            "ingestion_time": iso_now(),
        })
    return events

# Generate data
sales = generate_sales_events(50)
prices = generate_price_events(5)

print(f"Generated {len(sales)} sales events and {len(prices)} price events")

# COMMAND ----------

# Insert sales events into bronze
for event in sales:
    spark.sql(f"""
    INSERT INTO {SALES_TABLE}
    VALUES (
        '{event['event_id']}',
        {event['store_number']},
        '{event['event_timestamp']}',
        {event['item_id']},
        '{event['item_name']}',
        '{event['item_category']}',
        {event['quantity_sold']},
        {event['unit_price']},
        {event['total_amount']},
        '{event['cashier_id']}',
        '{event['transaction_id']}',
        '{event['ingestion_time']}'
    )
    """)

print(f"Inserted {len(sales)} sales events")

# COMMAND ----------

# Insert price events into bronze
for event in prices:
    spark.sql(f"""
    INSERT INTO {PRICE_TABLE}
    VALUES (
        '{event['event_id']}',
        '{event['event_timestamp']}',
        {event['item_id']},
        '{event['item_name']}',
        {event['old_price']},
        {event['new_price']},
        '{event['effective_date']}',
        '{event['ingestion_time']}'
    )
    """)

print(f"Inserted {len(prices)} price events")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 4 - Grant the Zerobus Publisher (service principal)
# MAGIC
# MAGIC The Zerobus publisher in Notebook 3 runs **from a laptop** and authenticates as a shared
# MAGIC workshop **service principal (SP)** - not as you. The SP can only write to these bronze tables
# MAGIC if it has been granted access. Run this once, after the tables exist.
# MAGIC
# MAGIC **Skip this if you are not doing the Zerobus lab** (Notebook 1's mock data is enough for the rest).
# MAGIC
# MAGIC Without this grant, the publisher fails with:
# MAGIC `401 invalid_authorization_details - User is not authorized to the requested authorizations`.
# MAGIC
# MAGIC Your workshop admin creates the SP once (see `SETUP_SERVICE_PRINCIPAL.md`) and gives you its
# MAGIC **application id**. Paste it below.

# COMMAND ----------

# The application id of the shared workshop Zerobus service principal.
# Ask your workshop admin for this value (see SETUP_SERVICE_PRINCIPAL.md).
ZEROBUS_SP = "<zerobus-sp-application-id>"   # e.g. "1b103dc1-cf0a-42ae-94ba-253f9ed2059d"

if ZEROBUS_SP and not ZEROBUS_SP.startswith("<"):
    spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{ZEROBUS_SP}`")
    spark.sql(f"GRANT USE SCHEMA  ON SCHEMA  {CATALOG}.bronze TO `{ZEROBUS_SP}`")
    spark.sql(f"GRANT SELECT, MODIFY ON SCHEMA {CATALOG}.bronze TO `{ZEROBUS_SP}`")
    print(f"Granted USE CATALOG + USE SCHEMA + SELECT, MODIFY on {CATALOG}.bronze to {ZEROBUS_SP}")
else:
    print("ZEROBUS_SP not set - skipping grant. Set it before running the Zerobus lab (Notebook 3).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 5 - Verify Setup

# COMMAND ----------

# Check bronze tables
print("=== Bronze Tables ===")
spark.sql(f"SELECT COUNT(*) as sales_events FROM {SALES_TABLE}").show()
spark.sql(f"SELECT COUNT(*) as price_updates FROM {PRICE_TABLE}").show()

print("\nSales events schema:")
spark.sql(f"DESC {SALES_TABLE}").display()

print("\nSample sales events:")
spark.sql(f"SELECT * FROM {SALES_TABLE} LIMIT 3").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup Complete!
# MAGIC
# MAGIC You now have (in **your own** catalog):
# MAGIC - Catalog: `publix_agentic_<yourname>`
# MAGIC - Schemas: `bronze` (raw landing), `medallion` (silver + gold)
# MAGIC - Tables: `bronze.sales_events` (~50 rows), `bronze.price_updates` (~5 rows)
# MAGIC
# MAGIC **Next steps:**
# MAGIC - **Notebook 2** - Run a Kafka producer locally to stream more events
# MAGIC - **Notebook 3** - Use Genie Code to build the Zerobus real-time ingest
# MAGIC - **Notebook 4** - Build the medallion pipeline with Spark Declarative Pipelines
# MAGIC - **Notebook 5** - Create a Genie space to query the gold layer
# MAGIC - **Notebook 6** - Build a Databricks App on top
