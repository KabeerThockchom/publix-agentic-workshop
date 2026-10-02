"""Publix synthetic data generator - Kafka-envelope shaped JSON events.

Generates realistic POSA sales and TPR price events that mirror customer data streams.
Writes events as JSON files to a UC Volume, one event per file (mimicking Kafka landing patterns).

POSA Sales envelope:
  {partition, offset, timestamp, timestampType, key, value}
  value = {Version, RequestId, TicketNumber, Username, TransactionDateTime, Basket, ReceiptText}
  Basket = {StoreNumber, LaneNumber, TransactionId, StartTime, EndTime, Subtotal, Total, Savings,
            TaxTotal, BasketItems[], BasketTenders[], CashierDetails[]}

TPR Price envelope:
  {key, data, topic, partition, offset, timestamp}
  data = {SystemId, EventType, Event_Id, Event_Timestamp, Item_Code, Store_Number, Price_Type,
          EventAction, Effective_Date, Term_Date, Selling_Price, Deal_Price, Break_Retail_Price,
          Sale_Quantity, Deal_Quantity, Mix_Match_Code, Vendor_Number, Created_By, Created_On}
  NOTE: Price/date fields in data are base64-encoded strings.
"""

import json
import random
import base64
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path
from typing import Generator, Dict, Any


# Publix product catalog (grocery items)
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
CASHIER_NAMES = ["Alice Johnson", "Bob Smith", "Carol Davis", "David Wilson", "Emma Brown"]
PAYMENT_METHODS = [
    {"name": "VISA", "brand": "Visa", "entry": "CHIP"},
    {"name": "MASTERCARD", "brand": "Mastercard", "entry": "TAP"},
    {"name": "DISCOVER", "brand": "Discover", "entry": "SWIPE"},
    {"name": "AMEX", "brand": "American Express", "entry": "CHIP"},
]
PRICE_TYPES = ["REGULAR", "DEAL", "CLEARANCE"]
PRICE_ACTIONS = ["CREATE", "UPDATE", "DELETE"]


def mask_card(card_num: str) -> str:
    """Mask card number for PII safety (last 4 digits only)."""
    return f"XXXX-XXXX-XXXX-{card_num[-4:]}"


def encode_field(value: str) -> str:
    """Base64 encode a field (for TPR price fields)."""
    return base64.b64encode(value.encode()).decode()


def generate_posa_sales_event() -> Dict[str, Any]:
    """Generate a single POSA sales event (Kafka envelope)."""
    now = datetime.utcnow()
    event_time = now - timedelta(seconds=random.randint(0, 3600))

    store_num = random.choice(STORE_NUMBERS)
    lane_num = random.randint(1, 6)
    cashier = random.choice(CASHIER_NAMES)

    # Basket items
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

    # Tenders
    payment = random.choice(PAYMENT_METHODS)
    card_num = "".join(random.choices("0123456789", k=16))
    approved_amount = round(subtotal * random.uniform(1.00, 1.10), 2)

    basket_tenders = [{
        "Name": payment["name"],
        "TenderType": "CARD",
        "ApprovedAmount": approved_amount,
        "PaymentDetails": {
            "CardBrand": payment["brand"],
            "MaskedCardNumber": mask_card(card_num),
            "EntryMethod": payment["entry"],
        }
    }]

    # Cashier details
    cashier_details = [{
        "Username": f"cashier_{random.randint(1000, 9999)}",
        "Name": cashier,
        "DateOfBirth": f"{random.randint(1975, 1995)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
    }]

    tax_total = round(subtotal * 0.07, 2)  # 7% tax
    savings = round(subtotal * random.uniform(0, 0.15), 2)

    basket = {
        "StoreNumber": store_num,
        "LaneNumber": lane_num,
        "TransactionId": str(uuid4().hex[:16]),
        "StartTime": (event_time).isoformat() + "Z",
        "EndTime": (event_time + timedelta(seconds=random.randint(30, 300))).isoformat() + "Z",
        "Subtotal": subtotal,
        "Total": round(subtotal + tax_total - savings, 2),
        "Savings": savings,
        "TaxTotal": tax_total,
        "BasketItems": basket_items,
        "BasketTenders": basket_tenders,
        "CashierDetails": cashier_details,
    }

    value = {
        "Version": "1.0",
        "RequestId": str(uuid4()),
        "TicketNumber": f"TKT-{store_num}-{random.randint(100000, 999999)}",
        "Username": f"user_{random.randint(1000, 9999)}",
        "TransactionDateTime": event_time.isoformat() + "Z",
        "Basket": basket,
        "ReceiptText": f"Thank you for shopping at Publix Store #{store_num}!",
    }

    # Kafka envelope
    return {
        "partition": random.randint(0, 3),
        "offset": random.randint(100000, 999999),
        "timestamp": int(event_time.timestamp() * 1000),
        "timestampType": 0,
        "key": f"{store_num}:{event_time.strftime('%Y%m%d')}",
        "value": value,
    }


def generate_tpr_price_event() -> Dict[str, Any]:
    """Generate a single TPR price event (Kafka envelope with base64-encoded fields)."""
    now = datetime.utcnow()
    event_time = now - timedelta(hours=random.randint(0, 24))

    prod = random.choice(PRODUCTS)
    store_num = random.choice(STORE_NUMBERS)
    price_type = random.choice(PRICE_TYPES)
    action = random.choice(PRICE_ACTIONS)

    # Generate base64-encoded price/date fields
    selling_price = round(prod["base_price"] * random.uniform(0.95, 1.15), 2)
    deal_price = round(selling_price * 0.90, 2) if price_type in ["DEAL", "CLEARANCE"] else None
    break_retail = round(selling_price * 1.05, 2)

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
        "EventAction": action,
        "Effective_Date": encode_field(effective_date.isoformat()),
        "Term_Date": encode_field(term_date.isoformat()),
        "Selling_Price": encode_field(str(selling_price)),
        "Deal_Price": encode_field(str(deal_price)) if deal_price else encode_field("0.00"),
        "Break_Retail_Price": encode_field(str(break_retail)),
        "Sale_Quantity": random.randint(1, 100),
        "Deal_Quantity": random.randint(0, 50),
        "Mix_Match_Code": f"MM{random.randint(100, 999)}",
        "Vendor_Number": f"VND{random.randint(10000, 99999)}",
        "Created_By": f"user_{random.randint(1000, 9999)}",
        "Created_On": encode_field(datetime.utcnow().isoformat() + "Z"),
    }

    # Kafka envelope
    return {
        "key": f"{prod['code']}:{store_num}",
        "data": data,
        "topic": "publix.pricing.updates",
        "partition": random.randint(0, 2),
        "offset": random.randint(50000, 499999),
        "timestamp": int(event_time.timestamp() * 1000),
    }


def generate_events_batch(
    num_sales: int = 100,
    num_prices: int = 20,
) -> Generator[tuple[str, Dict[str, Any]], None, None]:
    """Generate a batch of events.

    Yields (event_type, event_dict) tuples.
    event_type is 'sales' or 'price'.
    """
    sales_generated = 0
    prices_generated = 0

    # Interleave sales and price events
    while sales_generated < num_sales or prices_generated < num_prices:
        if sales_generated < num_sales and (prices_generated >= num_prices or random.random() < 0.8):
            yield ("sales", generate_posa_sales_event())
            sales_generated += 1
        elif prices_generated < num_prices:
            yield ("price", generate_tpr_price_event())
            prices_generated += 1


def write_events_to_volume(
    volume_path: Path,
    num_sales: int = 100,
    num_prices: int = 20,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Write generated events to a UC Volume as JSON files.

    Returns (num_sales_written, num_prices_written).
    """
    sales_dir = volume_path / "sales"
    price_dir = volume_path / "prices"

    if not dry_run:
        sales_dir.mkdir(parents=True, exist_ok=True)
        price_dir.mkdir(parents=True, exist_ok=True)

    sales_count = 0
    price_count = 0

    for event_type, event in generate_events_batch(num_sales, num_prices):
        if event_type == "sales":
            filename = f"sales_{datetime.utcnow().isoformat().replace(':', '-')}_{uuid4().hex[:8]}.json"
            filepath = sales_dir / filename
            if not dry_run:
                with open(filepath, "w") as f:
                    json.dump(event, f)
            sales_count += 1
        else:
            filename = f"price_{datetime.utcnow().isoformat().replace(':', '-')}_{uuid4().hex[:8]}.json"
            filepath = price_dir / filename
            if not dry_run:
                with open(filepath, "w") as f:
                    json.dump(event, f)
            price_count += 1

    return sales_count, price_count


if __name__ == "__main__":
    import sys

    # Usage: python publix_data_gen.py /path/to/volume [num_sales] [num_prices]
    if len(sys.argv) < 2:
        print("Usage: python publix_data_gen.py <volume_path> [num_sales] [num_prices]")
        print("Example: python publix_data_gen.py /Volumes/publix_demo/landing 100 20")
        sys.exit(1)

    volume_path = Path(sys.argv[1])
    num_sales = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    num_prices = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    sales_written, prices_written = write_events_to_volume(volume_path, num_sales, num_prices)
    print(f"Generated {sales_written} sales events and {prices_written} price events to {volume_path}")
