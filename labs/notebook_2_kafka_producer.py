# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 2 - Local Kafka Producer (Optional)
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** Run a synthetic Kafka producer locally on your laptop to stream real-time Publix sales
# MAGIC and price events. This notebook is **optional** - if you don't have Kafka set up, Notebook 3
# MAGIC (Zerobus) is the path forward.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - Kafka broker reachable at `KAFKA_BOOTSTRAP_SERVERS` (see configuration below)
# MAGIC - Python Kafka client: `pip install kafka-python` or `pip install confluent-kafka`
# MAGIC - ~60 seconds to run and stream events

# COMMAND ----------

# MAGIC %md
# MAGIC ## Your Catalog
# MAGIC
# MAGIC You all share one workspace, so each participant builds in their OWN catalog.
# MAGIC Run the next cell and type your first name in the `my_name` box that appears at the top.

# COMMAND ----------

dbutils.widgets.text("my_name", "", "Your first name (lowercase, no spaces)")
name = dbutils.widgets.get("my_name")
assert name and " " not in name, "Type your first name (lowercase, no spaces) in the my_name box at the top, then re-run."
CATALOG = f"publix_agentic_{name}"
print(f"Your catalog: {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration
# MAGIC
# MAGIC Edit the cell below to point at your Kafka broker. Three options:
# MAGIC
# MAGIC 1. **Local Docker Kafka** (easiest for testing):
# MAGIC    ```bash
# MAGIC    docker run -d --name kafka -p 9092:9092 confluentinc/cp-kafka:latest
# MAGIC    # Then set KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
# MAGIC    ```
# MAGIC
# MAGIC 2. **Local Redpanda** (simpler, no Docker):
# MAGIC    ```bash
# MAGIC    brew install redpanda-cli
# MAGIC    rpk redpanda start
# MAGIC    # Then set KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
# MAGIC    ```
# MAGIC
# MAGIC 3. **Publix production Kafka** (if reachable):
# MAGIC    ```
# MAGIC    KAFKA_BOOTSTRAP_SERVERS = "kafka1.publix.com:9092,kafka2.publix.com:9092"
# MAGIC    ```
# MAGIC
# MAGIC If you don't have Kafka, skip this notebook and use Notebook 3 (Zerobus ingest) instead.

# COMMAND ----------

# Configuration - EDIT THESE
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"  # Change to your Kafka broker
KAFKA_TOPIC_SALES = "publix-sales-events"
KAFKA_TOPIC_PRICES = "publix-price-updates"
DURATION_SECONDS = 60  # How long to produce events

# Databricks workspace details (for downstream consumption)
# Derives from your my_name widget set above
WORKSPACE_CATALOG = f"publix_agentic_{dbutils.widgets.get('my_name')}"

print(f"Kafka broker: {KAFKA_BOOTSTRAP_SERVERS}")
print(f"Topics: {KAFKA_TOPIC_SALES}, {KAFKA_TOPIC_PRICES}")
print(f"Duration: {DURATION_SECONDS} seconds")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install Kafka Client (if needed)
# MAGIC
# MAGIC Uncomment the line below if `kafka-python` is not installed.

# COMMAND ----------

# pip install kafka-python

# COMMAND ----------

# MAGIC %md
# MAGIC ## Start the Producer

# COMMAND ----------

import base64
import json
import random
import time
from datetime import datetime, timedelta
from uuid import uuid4
from kafka import KafkaProducer

# Product catalog - same shape as src/setup/publix_data_gen.py so these Kafka
# events match the POSA/TPR envelopes bronze + silver expect.
STORE_NUMBERS = [100, 102, 104, 106, 108, 110, 112, 114]
PRODUCTS = [
    {"code": "0071230002519", "sku": 1001, "name": "Boar's Head Deli Ham", "category": "Deli", "base_price": 6.99},
    {"code": "0041230001234", "sku": 1002, "name": "Publix Bakery Ciabatta", "category": "Bakery", "base_price": 2.49},
    {"code": "0041230004567", "sku": 1003, "name": "GreenWise Organic Milk", "category": "Dairy", "base_price": 4.29},
    {"code": "0078000073506", "sku": 1004, "name": "Coca-Cola 12-pack", "category": "Beverage", "base_price": 6.49},
    {"code": "0071230005678", "sku": 1005, "name": "Publix Hot Bar Sub", "category": "Deli", "base_price": 7.99},
    {"code": "0041230002111", "sku": 1006, "name": "Fresh Strawberries", "category": "Produce", "base_price": 3.99},
]
PRICE_TYPES = ["REGULAR", "DEAL", "CLEARANCE"]
PRICE_ACTIONS = ["CREATE", "UPDATE", "DELETE"]

def encode_field(value: str) -> str:
    """Base64-encode a TPR price/date field (bronze stores these raw)."""
    return base64.b64encode(value.encode()).decode()

def generate_sales_event():
    """Generate a single POSA sales event (Kafka envelope with nested Basket)."""
    event_time = datetime.utcnow() - timedelta(seconds=random.randint(0, 3600))
    store_num = random.choice(STORE_NUMBERS)

    basket_items = []
    subtotal = 0.0
    for _ in range(random.randint(1, 8)):
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
        "CashierDetails": [{"Username": f"cashier_{random.randint(1000, 9999)}", "Name": "Store Associate"}],
    }
    value = {
        "Version": "1.0",
        "RequestId": str(uuid4()),
        "TicketNumber": f"TKT-{store_num}-{random.randint(100000, 999999)}",
        "TransactionDateTime": event_time.isoformat() + "Z",
        "Basket": basket,
    }
    return {
        "partition": random.randint(0, 3),
        "offset": random.randint(100000, 999999),
        "timestamp": int(event_time.timestamp() * 1000),
        "timestampType": 0,
        "key": f"{store_num}:{event_time.strftime('%Y%m%d')}",
        "value": value,
    }

def generate_price_event():
    """Generate a single TPR price event (Kafka envelope, base64-encoded fields)."""
    event_time = datetime.utcnow() - timedelta(hours=random.randint(0, 24))
    prod = random.choice(PRODUCTS)
    store_num = random.choice(STORE_NUMBERS)
    price_type = random.choice(PRICE_TYPES)

    selling_price = round(prod["base_price"] * random.uniform(0.95, 1.15), 2)
    deal_price = round(selling_price * 0.90, 2) if price_type in ["DEAL", "CLEARANCE"] else 0.00
    effective_date = event_time.date()
    term_date = effective_date + timedelta(days=random.randint(7, 30))

    data = {
        "SystemId": "TPR_PRICING",
        "EventType": "PRICE_UPDATE",
        "Event_Id": str(uuid4()),
        "Event_Timestamp": encode_field(event_time.isoformat() + "Z"),
        "Item_Code": prod["code"],
        "Store_Number": store_num,
        "Price_Type": price_type,
        "EventAction": random.choice(PRICE_ACTIONS),
        "Effective_Date": encode_field(effective_date.isoformat()),
        "Term_Date": encode_field(term_date.isoformat()),
        "Selling_Price": encode_field(str(selling_price)),
        "Deal_Price": encode_field(str(deal_price)),
        "Break_Retail_Price": encode_field(str(round(selling_price * 1.05, 2))),
        "Created_By": f"user_{random.randint(1000, 9999)}",
        "Created_On": encode_field(datetime.utcnow().isoformat() + "Z"),
    }
    return {
        "key": f"{prod['code']}:{store_num}",
        "data": data,
        "topic": "publix.pricing.updates",
        "partition": random.randint(0, 2),
        "offset": random.randint(50000, 499999),
        "timestamp": int(event_time.timestamp() * 1000),
    }

try:
    # Connect to Kafka
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks='all',
    )
    print(f"[OK] Connected to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")

    # Produce events for DURATION_SECONDS
    start = time.time()
    sales_count = 0
    price_count = 0

    print(f"[*] Publishing events for {DURATION_SECONDS} seconds...")
    try:
        while time.time() - start < DURATION_SECONDS:
            # Generate 3-6 sales events per second
            for _ in range(random.randint(3, 6)):
                event = generate_sales_event()
                producer.send(KAFKA_TOPIC_SALES, value=event)
                sales_count += 1

            # Occasional price update (10% chance per second)
            if random.random() < 0.1:
                event = generate_price_event()
                producer.send(KAFKA_TOPIC_PRICES, value=event)
                price_count += 1

            time.sleep(1)

        # Flush remaining messages
        producer.flush()
        print(f"[OK] Published {sales_count} sales events and {price_count} price events")

    finally:
        producer.close()

except Exception as e:
    print(f"[ERROR] Could not connect to Kafka: {e}")
    print("\n[!] Kafka producer failed. Two options:")
    print("    1. Set up a local Kafka/Redpanda broker and retry (see config cell)")
    print("    2. Skip this notebook and use Notebook 3 (Zerobus ingest) instead")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Consumer (optional - verify data landed)
# MAGIC
# MAGIC If you want to verify events landed in your Kafka topic, run a quick consumer:
# MAGIC
# MAGIC ```python
# MAGIC from kafka import KafkaConsumer
# MAGIC import json
# MAGIC
# MAGIC consumer = KafkaConsumer(
# MAGIC     KAFKA_TOPIC_SALES,
# MAGIC     bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
# MAGIC     auto_offset_reset='earliest',
# MAGIC     value_deserializer=lambda m: json.loads(m.decode('utf-8'))
# MAGIC )
# MAGIC
# MAGIC for message in consumer:
# MAGIC     print(f"Topic: {message.topic}, Value: {message.value}")
# MAGIC     break  # Exit after 1 message
# MAGIC
# MAGIC consumer.close()
# MAGIC ```
# MAGIC
# MAGIC Or check your Kafka topic with the CLI:
# MAGIC ```
# MAGIC kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic publix-sales-events --from-beginning
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next Steps
# MAGIC
# MAGIC **If Kafka produced events:**
# MAGIC - Your events are in `publix-sales-events` and `publix-price-updates` topics
# MAGIC - Next, configure Notebook 3 (Zerobus ingest) to consume from these topics and write to `bronze.pos_sales_raw` / `bronze.price_updates_raw`
# MAGIC
# MAGIC **If Kafka did not work:**
# MAGIC - No problem! Proceed to Notebook 3 (Zerobus ingest) - it is the recommended path
# MAGIC - Notebook 1 (setup) already populated your bronze tables with synthetic data
# MAGIC
# MAGIC **Next:** Notebook 3 - Use Genie Code to build the real-time ingest pipeline
