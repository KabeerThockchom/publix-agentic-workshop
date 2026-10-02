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

import json
import random
import time
from datetime import datetime
from uuid import uuid4
from kafka import KafkaProducer

# Product catalog
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

def generate_sales_event():
    """Generate a single sales event."""
    p = random.choice(PRODUCTS)
    qty = random.randint(1, 10)
    return {
        "event_id": str(uuid4()),
        "store_number": random.choice(STORE_NUMBERS),
        "event_timestamp": iso_now(),
        "item_id": p["id"],
        "item_name": p["name"],
        "item_category": p["category"],
        "quantity_sold": qty,
        "unit_price": float(p["price"]),
        "total_amount": round(p["price"] * qty, 2),
        "cashier_id": f"C{random.randint(1000, 9999)}",
        "transaction_id": f"TX{uuid4().hex[:12]}",
        "ingestion_time": iso_now(),
    }

def generate_price_event():
    """Generate a single price update event."""
    p = random.choice(PRODUCTS)
    new_price = round(p["price"] * random.uniform(0.95, 1.05), 2)
    return {
        "event_id": str(uuid4()),
        "event_timestamp": iso_now(),
        "item_id": p["id"],
        "item_name": p["name"],
        "old_price": float(p["price"]),
        "new_price": new_price,
        "effective_date": datetime.utcnow().date().isoformat(),
        "ingestion_time": iso_now(),
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
