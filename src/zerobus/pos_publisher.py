"""StoreSight IQ - real-time POS event publisher (Zerobus).

Streams synthetic Publix POS + curbside/delivery events straight into the bronze
Delta table over Zerobus (serverless push ingest, no Kafka). The SDP/metric-view
layer reads these appends to keep the labor forecast current in real time.

Config comes from environment (no secrets in code):
  ZEROBUS_SERVER_ENDPOINT   https://<workspace-id>.zerobus.<region>.azuredatabricks.net
  DATABRICKS_WORKSPACE_URL  https://adb-<workspace-id>.<n>.azuredatabricks.net
  DATABRICKS_CLIENT_ID      service principal application id (MODIFY on the bronze table)
  DATABRICKS_CLIENT_SECRET  service principal secret
  TARGET_TABLE              default publix_technology.storesight_iq_publix.pos_events_bronze
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

TARGET_TABLE = os.environ.get(
    "TARGET_TABLE", "publix_technology.storesight_iq_publix.pos_events_bronze"
)
SERVER_ENDPOINT = os.environ["ZEROBUS_SERVER_ENDPOINT"]
WORKSPACE_URL = os.environ["DATABRICKS_WORKSPACE_URL"]
CLIENT_ID = os.environ["DATABRICKS_CLIENT_ID"]
CLIENT_SECRET = os.environ["DATABRICKS_CLIENT_SECRET"]
DURATION_SECONDS = int(os.environ.get("DURATION_SECONDS", "60"))

STORE_IDS = list(range(1, 25))  # 24 Publix stores
PRODUCTS = [
    {"id": 1, "name": "Pub Sub", "category": "Deli", "price": 7.49},
    {"id": 2, "name": "Rotisserie Chicken", "category": "Deli", "price": 8.99},
    {"id": 3, "name": "Chicken Tender Sub", "category": "Deli", "price": 8.49},
    {"id": 4, "name": "Publix Bakery Bread", "category": "Bakery", "price": 3.29},
    {"id": 5, "name": "GreenWise Organic Milk", "category": "Dairy", "price": 4.79},
    {"id": 6, "name": "Boar's Head Deli Ham", "category": "Deli", "price": 9.99},
    {"id": 7, "name": "Fresh Strawberries", "category": "Produce", "price": 3.99},
    {"id": 8, "name": "Publix Deli Platter", "category": "Deli", "price": 24.99},
]
# Channel mix: in-store dominant, curbside growing, delivery via Instacart.
CHANNELS = ["in_store"] * 78 + ["curbside"] * 15 + ["delivery"] * 7
PAYMENTS = ["card"] * 70 + ["app"] * 20 + ["cash"] * 10


def iso_now():
    return datetime.utcnow().isoformat() + "Z"


def main():
    sdk = ZerobusSdk(SERVER_ENDPOINT, WORKSPACE_URL)
    options = StreamConfigurationOptions(record_type=RecordType.JSON)
    stream = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, TableProperties(TARGET_TABLE), options)
    print(f"[*] Publishing synthetic Publix POS events for {DURATION_SECONDS}s -> {TARGET_TABLE}")

    count = 0
    start = time.time()
    try:
        while time.time() - start < DURATION_SECONDS:
            for _ in range(random.randint(3, 6)):  # 3-6 events/sec
                p = random.choice(PRODUCTS)
                qty = random.randint(1, 4)
                now = iso_now()
                stream.ingest_record_nowait({
                    "event_id": str(uuid4()),
                    "store_id": random.choice(STORE_IDS),
                    "event_timestamp": now,
                    "item_id": p["id"],
                    "item_name": p["name"],
                    "category": p["category"],
                    "channel": random.choice(CHANNELS),
                    "quantity": qty,
                    "unit_price": float(p["price"]),
                    "total": round(p["price"] * qty, 2),
                    "payment_method": random.choice(PAYMENTS),
                    "ingestion_time": now,
                })
                count += 1
            time.sleep(1)
        stream.flush()
        print(f"[OK] Published {count} POS events.")
    finally:
        stream.close()


if __name__ == "__main__":
    main()
