"""Lab 1 - Zerobus synthetic publisher.

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
    {"id": 1001, "name": "Boar's Head Deli Ham", "category": "Deli", "price": 6.99},
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
