"""Lab 3 - Zerobus synthetic publisher.

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
    {"code": "0071230002519", "sku": 1001, "name": "Boar's Head Deli Ham", "category": "Deli", "price": 6.99},
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
                "MaskedCardNumber": f"XXXX-XXXX-XXXX-{random.randint(1000, 9999)}",
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


def _generate_tpr_event(now):
    """Generate a TPR price event with base64-encoded fields."""
    event_time = now - timedelta(hours=random.randint(0, 24))
    prod = random.choice(PRODUCTS)
    store_num = random.choice(STORE_NUMBERS)

    selling_price = round(prod["price"] * random.uniform(0.95, 1.15), 2)

    return {
        "key": f"{prod['code']}:{store_num}",
        "data": {
            "SystemId": "TPR_PRICING",
            "EventType": "PRICE_UPDATE",
            "Event_Id": str(uuid4()),
            "Event_Timestamp": _encode_field(event_time.isoformat() + "Z"),
            "Item_Code": prod["code"],
            "Store_Number": store_num,
            "Price_Type": random.choice(PRICE_TYPES),
            "EventAction": "UPDATE",
            "Effective_Date": _encode_field(event_time.date().isoformat()),
            "Term_Date": _encode_field((event_time.date() + timedelta(days=30)).isoformat()),
            "Selling_Price": _encode_field(str(selling_price)),
            "Deal_Price": _encode_field(str(round(selling_price * 0.90, 2))),
            "Break_Retail_Price": _encode_field(str(round(selling_price * 1.05, 2))),
            "Sale_Quantity": random.randint(1, 100),
            "Deal_Quantity": random.randint(0, 50),
            "Mix_Match_Code": f"MM{random.randint(100, 999)}",
            "Vendor_Number": f"VND{random.randint(10000, 99999)}",
            "Created_By": f"user_{random.randint(1000, 9999)}",
            "Created_On": _encode_field(datetime.utcnow().isoformat() + "Z")
        },
        "topic": "publix.pricing.updates",
        "partition": random.randint(0, 2),
        "offset": random.randint(50000, 499999),
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
            if random.random() < 0.1:  # occasional price change
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
