# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ - Data Generation & Streaming Setup
# MAGIC 
# MAGIC This notebook:
# MAGIC 1. Creates the Unity Catalog schema
# MAGIC 2. Generates 1 year of synthetic QSR store data
# MAGIC 3. Sets up Lakebase instance for real-time streaming
# MAGIC 4. Creates streaming tables for live POS data
# MAGIC 
# MAGIC **Run this notebook first before starting the app!**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# Configuration — parameterized via the DAB job / notebook widgets.
dbutils.widgets.text("catalog", "publix_technology")
dbutils.widgets.text("schema", "storesight_iq_publix")
dbutils.widgets.text("resource_prefix", "storesight-publix")
dbutils.widgets.text("lakebase_database", "databricks_postgres")
# warehouse_id is REQUIRED to create the materialized views: MV DDL is not
# allowed on serverless generic/job compute (MV_NOT_ENABLED_ON_SERVERLESS_
# GENERIC_COMPUTE), so it runs on a SQL warehouse. The DAB passes var.warehouse_id.
dbutils.widgets.text("warehouse_id", "77b39aff2611a764")
dbutils.widgets.text("domain_json_path", "")

CATALOG_NAME = dbutils.widgets.get("catalog")
SCHEMA_NAME = dbutils.widgets.get("schema")
PREFIX = dbutils.widgets.get("resource_prefix")
WAREHOUSE_ID = dbutils.widgets.get("warehouse_id")

# Lakebase configuration (project-based instance; db defaults to databricks_postgres)
LAKEBASE_INSTANCE_NAME = f"{PREFIX}-oltp"
LAKEBASE_DATABASE_NAME = dbutils.widgets.get("lakebase_database")

# --- Load the single-source domain taxonomy (config/domain.json) ---
import json as _json
import os as _os

def _load_domain():
    cands = []
    _wp = dbutils.widgets.get("domain_json_path")
    if _wp:
        cands.append(_wp)
    cands += [
        "config/domain.json", "../config/domain.json", "./config/domain.json",
        _os.path.join(_os.getcwd(), "config", "domain.json"),
        _os.path.join(_os.path.dirname(_os.getcwd()), "config", "domain.json"),
    ]
    for p in cands:
        try:
            if p and _os.path.exists(p):
                with open(p) as f:
                    return _json.load(f)
        except Exception:
            pass
    raise FileNotFoundError(
        "config/domain.json not found. Pass the 'domain_json_path' widget "
        "(the DAB sets this to the synced repo path)."
    )

DOMAIN = _load_domain()

# Data generation settings (from the domain taxonomy)
NUM_STORES = len(DOMAIN["stores"])
DAYS_OF_HISTORY = DOMAIN.get("data_generation", {}).get("days_of_history", 365)
TRANSACTIONS_PER_DAY_AVG = DOMAIN.get("data_generation", {}).get("transactions_per_day_avg", 200)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create Unity Catalog Schema

# COMMAND ----------

# Use the existing catalog (already provisioned) and create our schema within it.
# NOTE: we do NOT CREATE CATALOG — the target catalog already exists and
# creating it fails when default storage isn't configured for the account.
spark.sql(f"USE CATALOG {CATALOG_NAME}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}")
spark.sql(f"USE SCHEMA {SCHEMA_NAME}")

print(f"✓ Using catalog: {CATALOG_NAME}")
print(f"✓ Created schema: {SCHEMA_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Define Store Locations

# COMMAND ----------

from pyspark.sql.types import *
from pyspark.sql import functions as F
from datetime import datetime, timedelta
import random

# Store locations — sourced from the domain taxonomy (config/domain.json).
stores_data = [
    (
        s["id"], s["name"], s.get("address", ""), s.get("city", ""),
        s.get("state", ""), float(s["lat"]), float(s["lng"]),
        int(s.get("sqft", 1400)), s.get("opened", "2020-01-01"),
    )
    for s in DOMAIN["stores"]
]

stores_schema = StructType([
    StructField("store_id", IntegerType(), False),
    StructField("name", StringType(), False),
    StructField("address", StringType(), False),
    StructField("city", StringType(), False),
    StructField("state", StringType(), False),
    StructField("latitude", DoubleType(), False),
    StructField("longitude", DoubleType(), False),
    StructField("sqft", IntegerType(), False),
    StructField("open_date", StringType(), False),
])

stores_df = spark.createDataFrame(stores_data, stores_schema)
stores_df.write.mode("overwrite").saveAsTable("stores")
print(f"✓ Created stores table with {stores_df.count()} stores")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Define Menu Items and Ingredients

# COMMAND ----------

# Menu items — the customer's real products from domain.menu_items (falls back
# to the prep subtype labels), plus a few generic side/beverage items.
menu_items = []
_mid = 1
_main = DOMAIN.get("menu_items") or [f"{_s['label']} — Signature" for _s in DOMAIN["prep"]["subtypes"]]
for _name in _main:
    menu_items.append((_mid, _name, "main", 12.99, 15.99))
    _mid += 1
menu_items += [
    (_mid, "Side Item", "side", 6.49, 6.49),
    (_mid + 1, "Dessert", "side", 8.99, 8.99),
    (_mid + 2, "Fountain Drink", "beverage", 2.49, 2.49),
    (_mid + 3, "Bottled Water", "beverage", 2.29, 2.29),
]

menu_schema = StructType([
    StructField("item_id", IntegerType(), False),
    StructField("item_name", StringType(), False),
    StructField("category", StringType(), False),
    StructField("price_medium", DoubleType(), False),
    StructField("price_large", DoubleType(), False),
])

menu_df = spark.createDataFrame(menu_items, menu_schema)
menu_df.write.mode("overwrite").saveAsTable("menu_items")
print(f"✓ Created menu_items table with {menu_df.count()} items")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Generate Historical POS Transactions

# COMMAND ----------

import uuid
from datetime import datetime, timedelta
import random

def generate_transactions(num_days=365, avg_daily_txns=200):
    """Generate realistic POS transactions with daypart patterns."""
    
    transactions = []
    line_items = []
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=num_days)
    
    txn_id = 1
    line_id = 1
    
    for day_offset in range(num_days):
        current_date = start_date + timedelta(days=day_offset)
        day_of_week = current_date.weekday()
        
        # Fewer transactions on weekends
        if day_of_week >= 5:
            daily_txns = int(avg_daily_txns * 0.75)
        else:
            daily_txns = avg_daily_txns
        
        for store_id in range(1, NUM_STORES + 1):
            # Store performance variation
            store_multiplier = 0.8 + (store_id % 5) * 0.1
            store_txns = int(daily_txns * store_multiplier * random.uniform(0.9, 1.1))
            
            for _ in range(store_txns):
                # Generate transaction time based on daypart
                hour = random.choices(
                    range(6, 22),
                    weights=[
                        3, 5, 7, 8,  # 6-9 AM (breakfast)
                        12, 18, 20, 18,  # 10 AM - 1 PM (lunch rush)
                        10, 8, 8,  # 2-4 PM (afternoon)
                        12, 15, 14, 10,  # 5-8 PM (dinner)
                        5  # 9 PM
                    ]
                )[0]
                minute = random.randint(0, 59)
                
                txn_time = current_date.replace(hour=hour, minute=minute)
                
                # Channel distribution
                channel = random.choices(
                    ["in_store", "delivery", "app", "third_party"],
                    weights=[30, 40, 18, 12]
                )[0]

                payment = random.choices(
                    ["credit", "debit", "cash", "apple_pay", "google_pay"],
                    weights=[40, 25, 20, 10, 5]
                )[0]

                # Generate line items (1-3 mains + optional sides)
                num_mains = random.randint(1, 3)
                total = 0

                for _ in range(num_mains):
                    item_id = random.randint(1, len(menu_items))  # main/menu items
                    is_large = random.random() > 0.4
                    price = menu_items[item_id-1][4] if is_large else menu_items[item_id-1][3]

                    line_items.append((
                        line_id,
                        txn_id,
                        item_id,
                        menu_items[item_id-1][1],
                        1,
                        price,
                        "large" if is_large else "medium"
                    ))
                    total += price
                    line_id += 1

                # Add sides/drinks — pick from the actual generic (non-main) menu
                # items, so this is safe for any menu length (no hardcoded ids).
                if random.random() > 0.4:
                    for _m in [m for m in menu_items if m[2] in ("side", "beverage")]:
                        if random.random() > 0.5:
                            price = _m[3]
                            line_items.append((
                                line_id,
                                txn_id,
                                _m[0],
                                _m[1],
                                1,
                                price,
                                None
                            ))
                            total += price
                            line_id += 1
                
                transactions.append((
                    txn_id,
                    store_id,
                    txn_time.isoformat(),
                    round(total, 2),
                    channel,
                    payment
                ))
                txn_id += 1
        
        if day_offset % 30 == 0:
            print(f"  Generated {day_offset}/{num_days} days...")
    
    return transactions, line_items

print("Generating transaction history (this may take a few minutes)...")
transactions, line_items = generate_transactions(DAYS_OF_HISTORY, TRANSACTIONS_PER_DAY_AVG)
print(f"✓ Generated {len(transactions)} transactions with {len(line_items)} line items")

# COMMAND ----------

# Save transactions to Delta table
txn_schema = StructType([
    StructField("txn_id", IntegerType(), False),
    StructField("store_id", IntegerType(), False),
    StructField("timestamp", StringType(), False),
    StructField("total", DoubleType(), False),
    StructField("channel", StringType(), False),
    StructField("payment_method", StringType(), False),
])

txn_df = spark.createDataFrame(transactions, txn_schema)
txn_df = txn_df.withColumn("timestamp", F.to_timestamp("timestamp"))
txn_df.write.mode("overwrite").partitionBy("store_id").saveAsTable("pos_transactions")
print(f"✓ Created pos_transactions table")

# Save line items
line_schema = StructType([
    StructField("line_id", IntegerType(), False),
    StructField("txn_id", IntegerType(), False),
    StructField("item_id", IntegerType(), False),
    StructField("item_name", StringType(), False),
    StructField("quantity", IntegerType(), False),
    StructField("price", DoubleType(), False),
    StructField("modifier", StringType(), True),
])

line_df = spark.createDataFrame(line_items, line_schema)
line_df.write.mode("overwrite").saveAsTable("pos_line_items")
print(f"✓ Created pos_line_items table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Generate Employee and Labor Data

# COMMAND ----------

# Generate employees
employees = []
roles = ["shift_lead", "prep_cook", "cashier"]
first_names = ["Maria", "John", "Sarah", "Mike", "Emily", "David", "Jessica", "Chris", "Amanda", "Ryan"]
last_names = ["Garcia", "Davis", "Kim", "Rodriguez", "Chen", "Park", "Lee", "Brown", "Wilson", "Martinez"]

emp_id = 1
for store_id in range(1, NUM_STORES + 1):
    num_employees = random.randint(6, 10)
    for _ in range(num_employees):
        role = random.choices(roles, weights=[20, 60, 20])[0]
        hourly_rate = {"shift_lead": 18.50, "prep_cook": 16.00, "cashier": 15.00}[role]
        
        employees.append((
            emp_id,
            store_id,
            f"{random.choice(first_names)} {random.choice(last_names)}",
            role,
            hourly_rate,
            random.choice(["full_time", "part_time"]),
            "active"
        ))
        emp_id += 1

emp_schema = StructType([
    StructField("employee_id", IntegerType(), False),
    StructField("store_id", IntegerType(), False),
    StructField("name", StringType(), False),
    StructField("role", StringType(), False),
    StructField("hourly_rate", DoubleType(), False),
    StructField("employment_type", StringType(), False),
    StructField("status", StringType(), False),
])

emp_df = spark.createDataFrame(employees, emp_schema)
emp_df.write.mode("overwrite").saveAsTable("employees")
print(f"✓ Created employees table with {emp_df.count()} employees")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5b. Generate Labor Schedule Data

# COMMAND ----------

# Generate historical and future labor schedules (hourly staffing levels)
# This provides the "scheduled" staff counts for the Hourly Staffing component

labor_schedules = []

# Generate schedules for the past 30 days and next 7 days
schedule_start = datetime.now() - timedelta(days=30)
schedule_end = datetime.now() + timedelta(days=7)
num_schedule_days = (schedule_end - schedule_start).days

for day_offset in range(num_schedule_days):
    current_date = schedule_start + timedelta(days=day_offset)
    date_str = current_date.strftime("%Y-%m-%d")
    day_of_week = current_date.weekday()
    is_weekend = day_of_week >= 5
    
    for store_id in range(1, NUM_STORES + 1):
        # Store size affects base staffing
        store_multiplier = 0.9 + (store_id % 5) * 0.05
        
        for hour in range(6, 22):  # Operating hours 6 AM to 10 PM
            # Base staffing varies by daypart
            if 11 <= hour < 14:  # Lunch rush
                base_scheduled = 6
            elif 17 <= hour < 20:  # Dinner rush
                base_scheduled = 5
            elif 7 <= hour < 10:  # Breakfast
                base_scheduled = 3
            else:  # Off-peak
                base_scheduled = 3
            
            # Weekend adjustment (slightly lower)
            if is_weekend:
                base_scheduled = max(2, base_scheduled - 1)
            
            # Apply store multiplier and add some variance
            scheduled = max(2, min(8, int(base_scheduled * store_multiplier + random.uniform(-0.5, 0.5))))
            
            # For past dates, generate actual staff (may differ slightly from scheduled)
            if current_date.date() < datetime.now().date():
                # Actual may vary by ±1 from scheduled
                actual = max(1, scheduled + random.choice([-1, 0, 0, 0, 1]))
            else:
                actual = None  # Future dates don't have actuals yet
            
            labor_schedules.append((
                store_id,
                date_str,
                hour,
                f"{hour}:00" if hour < 12 else f"{hour-12 if hour > 12 else 12}:00 PM" if hour >= 12 else f"{hour}:00 AM",
                scheduled,
                actual
            ))

labor_schema = StructType([
    StructField("store_id", IntegerType(), False),
    StructField("date", StringType(), False),
    StructField("hour", IntegerType(), False),
    StructField("hour_label", StringType(), False),
    StructField("scheduled_staff", IntegerType(), False),
    StructField("actual_staff", IntegerType(), True),
])

labor_df = spark.createDataFrame(labor_schedules, labor_schema)
labor_df.write.mode("overwrite").partitionBy("store_id", "date").saveAsTable("labor_schedule")
print(f"✓ Created labor_schedule table with {labor_df.count()} hourly records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Generate Inventory Data

# COMMAND ----------

# Ingredients — sourced from the domain taxonomy (config/domain.json).
ingredients = [
    (i["id"], i["name"], i["category"], i["unit"], i["cost_per_unit"])
    for i in DOMAIN["ingredients"]
]

ing_schema = StructType([
    StructField("ingredient_id", IntegerType(), False),
    StructField("name", StringType(), False),
    StructField("category", StringType(), False),
    StructField("unit", StringType(), False),
    StructField("cost_per_unit", DoubleType(), False),
])

ing_df = spark.createDataFrame(ingredients, ing_schema)
ing_df.write.mode("overwrite").saveAsTable("ingredients")
print(f"✓ Created ingredients table")

# Generate current inventory levels
inventory_levels = []
for store_id in range(1, NUM_STORES + 1):
    for ing_id, name, cat, unit, cost in ingredients:
        par_level = random.randint(10, 30)
        current = par_level * random.uniform(0.3, 1.2)
        inventory_levels.append((
            store_id,
            ing_id,
            datetime.now().strftime("%Y-%m-%d"),
            round(current, 1),
            par_level,
            round(current / (par_level / 3), 1)  # days_supply
        ))

inv_schema = StructType([
    StructField("store_id", IntegerType(), False),
    StructField("ingredient_id", IntegerType(), False),
    StructField("date", StringType(), False),
    StructField("qty_on_hand", DoubleType(), False),
    StructField("par_level", IntegerType(), False),
    StructField("days_supply", DoubleType(), False),
])

inv_df = spark.createDataFrame(inventory_levels, inv_schema)
inv_df.write.mode("overwrite").saveAsTable("inventory_levels")
print(f"✓ Created inventory_levels table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Create Aggregated Views for Dashboards

# COMMAND ----------

# Store KPI view.
# IMPORTANT: "today/yesterday/wtd/mtd/ytd" are anchored to the LATEST date present
# in the data (MAX(DATE(timestamp))), NOT CURRENT_DATE(). The synthetic data is
# static, so a calendar-date anchor makes every store show $0 / -100% a day after
# generation. Anchoring to the data's max date keeps the demo correct on any day.
spark.sql("""
CREATE OR REPLACE VIEW stores_kpi_view AS
WITH md AS (SELECT MAX(DATE(timestamp)) AS d FROM pos_transactions),
t AS (
    SELECT
        p.store_id,
        SUM(CASE WHEN DATE(p.timestamp) = md.d THEN p.total ELSE 0 END) as sales_today,
        SUM(CASE WHEN DATE(p.timestamp) = DATE_SUB(md.d, 1) THEN p.total ELSE 0 END) as sales_yesterday,
        SUM(CASE WHEN WEEKOFYEAR(p.timestamp) = WEEKOFYEAR(md.d) AND YEAR(p.timestamp) = YEAR(md.d) THEN p.total ELSE 0 END) as sales_wtd,
        SUM(CASE WHEN MONTH(p.timestamp) = MONTH(md.d) AND YEAR(p.timestamp) = YEAR(md.d) THEN p.total ELSE 0 END) as sales_mtd,
        SUM(CASE WHEN YEAR(p.timestamp) = YEAR(md.d) THEN p.total ELSE 0 END) as sales_ytd
    FROM pos_transactions p CROSS JOIN md
    GROUP BY p.store_id
),
-- Seasonally-fair baseline: each store's average sales on the SAME weekday over
-- the trailing 28 days. The trend/"vs Forecast" metric compares today to this,
-- NOT to raw yesterday — otherwise a Monday-vs-Sunday comparison makes every
-- store look "up" (day-of-week noise) and the map is uniformly green.
base AS (
    SELECT d.store_id, AVG(d.daily_s) AS avg_same_dow
    FROM (
        SELECT store_id, DATE(timestamp) AS dt, SUM(total) AS daily_s
        FROM pos_transactions GROUP BY store_id, DATE(timestamp)
    ) d CROSS JOIN md
    WHERE d.dt < md.d AND d.dt >= DATE_SUB(md.d, 28) AND DAYOFWEEK(d.dt) = DAYOFWEEK(md.d)
    GROUP BY d.store_id
)
SELECT
    s.store_id,
    s.name,
    s.city,
    s.latitude,
    s.longitude,
    COALESCE(t.sales_today, 0) as sales_today,
    COALESCE(t.sales_yesterday, 0) as sales_yesterday,
    COALESCE(t.sales_wtd, 0) as sales_wtd,
    COALESCE(t.sales_mtd, 0) as sales_mtd,
    COALESCE(t.sales_ytd, 0) as sales_ytd,
    ROUND((COALESCE(t.sales_today, 0) - b.avg_same_dow) / NULLIF(b.avg_same_dow, 0) * 100, 1) as vs_yesterday_pct,
    25.0 as labor_cost_pct,
    ROW_NUMBER() OVER (ORDER BY COALESCE(t.sales_mtd, 0) DESC) as rank
FROM stores s
LEFT JOIN t ON s.store_id = t.store_id
LEFT JOIN base b ON s.store_id = b.store_id
""")
print("✓ Created stores_kpi_view (anchored to latest data date)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Materialized Views (fast, pre-aggregated — the app + Genie read these)

# COMMAND ----------

# Materialized views pre-aggregate the heavy pos_transactions rollups so the app's
# KPI/map/compare cards and the Genie space are fast (raw tables have ~NUM_STORES x
# 365 x txns/day rows). mv_store_overview reads stores_kpi_view, so it MUST be
# created after the view above. Schema-qualified so they match how the app queries.
#
# MV creation/refresh is NOT permitted on serverless generic/job compute
# (MV_NOT_ENABLED_ON_SERVERLESS_GENERIC_COMPUTE), so the DDL is executed on the
# SQL WAREHOUSE via the Statement Execution API (real materialized views, backed
# by a managed refresh) rather than this notebook's spark session.
_FQ = f"{CATALOG_NAME}.{SCHEMA_NAME}"

_MVS = {
    "mv_daily_sales": f"""
        SELECT t.store_id, s.name AS store_name, s.city, CAST(t.timestamp AS DATE) AS sale_date,
               t.channel, t.payment_method,
               COUNT(*) AS transaction_count, SUM(t.total) AS total_sales, AVG(t.total) AS avg_ticket
        FROM {_FQ}.pos_transactions t
        LEFT JOIN {_FQ}.stores s ON t.store_id = s.store_id
        GROUP BY t.store_id, s.name, s.city, CAST(t.timestamp AS DATE), t.channel, t.payment_method
    """,
    "mv_employees": f"""
        SELECT e.store_id, s.name AS store_name, s.city, e.name AS employee_name,
               e.role, e.hourly_rate, e.employment_type, e.status
        FROM {_FQ}.employees e
        LEFT JOIN {_FQ}.stores s ON e.store_id = s.store_id
    """,
    "mv_inventory": f"""
        SELECT i.store_id, s.name AS store_name, s.city, i.ingredient_id, i.date AS snapshot_date,
               i.qty_on_hand, i.par_level, i.days_supply,
               CASE WHEN i.qty_on_hand < i.par_level THEN true ELSE false END AS below_par
        FROM {_FQ}.inventory_levels i
        LEFT JOIN {_FQ}.stores s ON i.store_id = s.store_id
    """,
    # mv_store_overview reads the (max-date-anchored) stores_kpi_view + rollups.
    "mv_store_overview": f"""
        SELECT s.store_id, s.name AS store_name, s.address, s.city, s.state, s.latitude, s.longitude,
               s.sqft, s.open_date,
               k.sales_today, k.sales_yesterday, k.sales_wtd, k.sales_mtd, k.sales_ytd,
               k.vs_yesterday_pct, k.labor_cost_pct, k.rank,
               e.employee_count, e.full_time_count, e.part_time_count, e.avg_hourly_rate,
               i.ingredient_count, i.items_below_par, i.avg_days_supply
        FROM {_FQ}.stores s
        LEFT JOIN {_FQ}.stores_kpi_view k ON s.store_id = k.store_id
        LEFT JOIN (
            SELECT store_id, COUNT(*) AS employee_count,
                   SUM(CASE WHEN employment_type='full_time' THEN 1 ELSE 0 END) AS full_time_count,
                   SUM(CASE WHEN employment_type='part_time' THEN 1 ELSE 0 END) AS part_time_count,
                   AVG(hourly_rate) AS avg_hourly_rate
            FROM {_FQ}.employees GROUP BY store_id
        ) e ON s.store_id = e.store_id
        LEFT JOIN (
            SELECT store_id, COUNT(DISTINCT ingredient_id) AS ingredient_count,
                   SUM(CASE WHEN qty_on_hand < par_level THEN 1 ELSE 0 END) AS items_below_par,
                   AVG(days_supply) AS avg_days_supply
            FROM {_FQ}.inventory_levels GROUP BY store_id
        ) i ON s.store_id = i.store_id
    """,
}
if not WAREHOUSE_ID:
    raise ValueError(
        "warehouse_id is required to create the materialized views (MV DDL is not "
        "allowed on serverless generic/job compute). The DAB passes var.warehouse_id; "
        "set the widget when running this notebook standalone."
    )

from databricks.sdk import WorkspaceClient as _WC
from databricks.sdk.service.sql import StatementState as _SS
import time as _time

_wh = _WC()

def _run_on_warehouse(_stmt):
    """Execute DDL on the SQL warehouse (not serverless generic compute) and
    block until it finishes — MV create/refresh is only allowed on a warehouse."""
    r = _wh.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID, statement=_stmt, wait_timeout="50s"
    )
    while r.status and r.status.state in (_SS.PENDING, _SS.RUNNING):
        _time.sleep(3)
        r = _wh.statement_execution.get_statement(r.statement_id)
    _state = r.status.state if r.status else None
    if _state != _SS.SUCCEEDED:
        _msg = r.status.error.message if (r.status and r.status.error) else str(_state)
        raise RuntimeError(f"Warehouse statement failed ({_state}): {_msg}\nSQL: {_stmt[:160]}")
    return r

for _name, _sel in _MVS.items():
    _run_on_warehouse(f"DROP MATERIALIZED VIEW IF EXISTS {_FQ}.{_name}")
    _run_on_warehouse(f"CREATE MATERIALIZED VIEW {_FQ}.{_name} AS {_sel}")
    print(f"✓ Created materialized view {_name} (on SQL warehouse {WAREHOUSE_ID})")

# NOTE: MVs are a point-in-time snapshot. They do NOT auto-update, so after
# changing stores_kpi_view, or after any new data load (including the nb07
# streaming sim, which appends rows), run:
#   REFRESH MATERIALIZED VIEW {CATALOG}.{SCHEMA}.mv_store_overview   (and the others)
# nb07 refreshes them after its append; schedule a periodic REFRESH if streaming
# runs continuously.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7b. Create Streaming Simulation Table
# MAGIC 
# MAGIC This creates a `pos_transactions_stream` table that simulates real-time streaming POS data.
# MAGIC The table contains the most recent transactions and is designed to be refreshed every 10 seconds.

# COMMAND ----------

# Create streaming simulation table with recent transactions
# This acts as a "live" view of the most recent transactions

spark.sql(f"""
CREATE OR REPLACE TABLE pos_transactions_stream AS
SELECT 
    txn_id,
    store_id,
    -- Shift timestamps to make them appear recent (today)
    TIMESTAMP(CONCAT(CURRENT_DATE(), ' ', DATE_FORMAT(timestamp, 'HH:mm:ss'))) as timestamp,
    total,
    channel,
    payment_method
FROM pos_transactions
WHERE DATE(timestamp) = (SELECT MAX(DATE(timestamp)) FROM pos_transactions)
ORDER BY timestamp DESC
LIMIT 5000
""")

# Update the timestamps to be distributed throughout today up to current time.
# Compute an integer seconds-offset from midnight for each row, then add it to
# midnight via unix-timestamp arithmetic (Spark SQL does not accept a dynamic
# expression inside INTERVAL ... SECOND, so we build the timestamp numerically).
spark.sql(f"""
MERGE INTO pos_transactions_stream AS target
USING (
    SELECT
        txn_id,
        CAST(
            from_unixtime(
                unix_timestamp(TIMESTAMP(CURRENT_DATE()))
                + CAST(
                    ROW_NUMBER() OVER (ORDER BY timestamp DESC)
                    * (unix_timestamp(CURRENT_TIMESTAMP()) - unix_timestamp(TIMESTAMP(CURRENT_DATE())))
                    / COUNT(*) OVER ()
                  AS BIGINT)
            ) AS TIMESTAMP
        ) as new_timestamp
    FROM pos_transactions_stream
) AS source
ON target.txn_id = source.txn_id
WHEN MATCHED THEN UPDATE SET timestamp = source.new_timestamp
""")

stream_count = spark.sql("SELECT COUNT(*) as cnt FROM pos_transactions_stream").first().cnt
print(f"✓ Created pos_transactions_stream table with {stream_count:,} simulated live transactions")
print("  This table simulates real-time POS data for the Operations page")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Streaming Table Refresh Function
# MAGIC 
# MAGIC Run this cell periodically (e.g., every 10 seconds) to simulate new incoming transactions.
# MAGIC In production, this would be replaced by actual streaming data from POS systems.

# COMMAND ----------

def refresh_streaming_table():
    """
    Refreshes the streaming table with new simulated transactions.
    Call this function every 10 seconds to simulate live data.
    """
    import random
    from datetime import datetime
    
    # Generate a few new transactions for each store
    new_txns = []
    base_txn_id = spark.sql("SELECT MAX(txn_id) as max_id FROM pos_transactions_stream").first().max_id or 0
    
    now = datetime.now()
    
    for store_id in range(1, NUM_STORES + 1):
        # Each store gets 0-3 new transactions per refresh
        num_new = random.randint(0, 3)
        for i in range(num_new):
            base_txn_id += 1
            # Random time in the last 10 seconds
            seconds_ago = random.randint(0, 10)
            txn_time = now - timedelta(seconds=seconds_ago)
            
            total = round(random.uniform(8.99, 24.99), 2)
            channel = random.choices(
                ["in_store", "delivery", "app", "third_party"],
                weights=[30, 40, 18, 12]
            )[0]
            payment = random.choices(
                ["credit", "debit", "cash", "apple_pay", "google_pay"],
                weights=[40, 25, 20, 10, 5]
            )[0]
            
            new_txns.append((base_txn_id, store_id, txn_time.isoformat(), total, channel, payment))
    
    if new_txns:
        # Insert new transactions
        new_df = spark.createDataFrame(new_txns, ["txn_id", "store_id", "timestamp", "total", "channel", "payment_method"])
        new_df = new_df.withColumn("timestamp", F.to_timestamp("timestamp"))
        new_df.write.mode("append").saveAsTable("pos_transactions_stream")
        
        # Keep only the most recent 5000 transactions to prevent unbounded growth
        spark.sql("""
            DELETE FROM pos_transactions_stream 
            WHERE txn_id NOT IN (
                SELECT txn_id FROM pos_transactions_stream 
                ORDER BY timestamp DESC 
                LIMIT 5000
            )
        """)
        
        print(f"✓ Added {len(new_txns)} new transactions at {now.strftime('%H:%M:%S')}")
    else:
        print(f"  No new transactions this cycle at {now.strftime('%H:%M:%S')}")

# Run once to demonstrate
refresh_streaming_table()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Auto-Refresh Loop (Optional)
# MAGIC 
# MAGIC Uncomment and run this cell to continuously refresh the streaming table every 10 seconds.
# MAGIC **Stop the cell manually when done testing.**

# COMMAND ----------

# # Uncomment to run continuous streaming simulation
# import time
# 
# print("Starting streaming simulation (Ctrl+C or stop cell to end)...")
# try:
#     while True:
#         refresh_streaming_table()
#         time.sleep(10)  # Wait 10 seconds between refreshes
# except KeyboardInterrupt:
#     print("\nStreaming simulation stopped.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Setup Lakebase Instance (Optional - for real-time streaming)
# MAGIC 
# MAGIC This section creates a Lakebase PostgreSQL instance and syncs your Delta tables.
# MAGIC 
# MAGIC **⚠️ Cost Warning:** Lakebase instances incur ongoing costs. Delete when no longer needed.
# MAGIC 
# MAGIC Reference: [Databricks Apps Cookbook - Lakebase](https://apps-cookbook.dev/docs/fastapi/building_endpoints/lakebase/lakebase_resources_create/)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8a. Check SDK Version & Install Dependencies
# MAGIC 
# MAGIC Lakebase requires `databricks-sdk>=0.60.0`. Run this cell first to ensure you have the correct version.

# COMMAND ----------

# Check and upgrade databricks-sdk if needed
import subprocess
import sys

# Check current version
try:
    import databricks.sdk
    current_version = databricks.sdk.__version__
    print(f"Current databricks-sdk version: {current_version}")
    
    # Parse version
    major, minor, patch = map(int, current_version.split('.')[:3])
    if major == 0 and minor < 60:
        print(f"⚠️ Lakebase requires databricks-sdk>=0.60.0")
        print("Upgrading databricks-sdk...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "databricks-sdk>=0.60.0", "-q"])
        print("✓ Upgraded! Please RESTART your cluster for changes to take effect.")
    else:
        print("✓ SDK version is compatible with Lakebase")
except Exception as e:
    print(f"Installing databricks-sdk...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "databricks-sdk>=0.60.0", "-q"])
    print("✓ Installed! Please RESTART your cluster for changes to take effect.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8b. Initialize Lakebase Client
# MAGIC 
# MAGIC **⚠️ If you see import errors, restart your cluster after the SDK upgrade above.**

# COMMAND ----------

from databricks.sdk import WorkspaceClient

# Initialize Workspace client
w = WorkspaceClient()
current_user = w.current_user.me()
print(f"✓ Authenticated as: {current_user.user_name}")

# Try to import Lakebase modules
LAKEBASE_AVAILABLE = False
try:
    from databricks.sdk.service.database import (
        DatabaseCatalog,
        DatabaseInstance,
        DatabaseInstanceRole,
        DatabaseInstanceRoleAttributes,
        DatabaseInstanceRoleIdentityType,
        DatabaseInstanceRoleMembershipRole,
        NewPipelineSpec,
        SyncedDatabaseTable,
        SyncedTableSchedulingPolicy,
        SyncedTableSpec,
    )
    LAKEBASE_AVAILABLE = True
    print("✓ Lakebase modules loaded successfully")
except ImportError as e:
    print(f"✗ Lakebase modules not available: {e}")
    print("\n⚠️ To fix this:")
    print("  1. Run the cell above to upgrade databricks-sdk")
    print("  2. RESTART your cluster (Compute > your cluster > Restart)")
    print("  3. Re-run this notebook from section 8a")
    print("\n  OR if Lakebase is not enabled in your workspace:")
    print("  - Contact your Databricks admin to enable Lakebase")
    print("  - Skip section 8 and proceed to section 9")

# Lakebase configuration
LAKEBASE_PG_CATALOG = f"{LAKEBASE_INSTANCE_NAME}-pg-catalog"

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8c. Create Lakebase Database Instance
# MAGIC 
# MAGIC This creates the PostgreSQL database instance. **This may take 5-10 minutes.**

# COMMAND ----------

# Check if instance already exists
if not LAKEBASE_AVAILABLE:
    print("⚠️ Skipping - Lakebase modules not available. See section 8b above.")
else:
    instance_exists = False
    try:
        existing = w.database.get_database_instance(name=LAKEBASE_INSTANCE_NAME)
        instance_exists = True
        print(f"✓ Lakebase instance '{LAKEBASE_INSTANCE_NAME}' already exists")
        print(f"  Status: {existing.status}")
        print(f"  DNS: {existing.read_write_dns}")
    except Exception as e:
        if "not found" in str(e).lower() or "404" in str(e):
            print(f"Instance '{LAKEBASE_INSTANCE_NAME}' not found. Will create new instance...")
        else:
            print(f"Error checking instance: {e}")

# COMMAND ----------

# Create new instance if it doesn't exist
if not LAKEBASE_AVAILABLE:
    print("⚠️ Skipping - Lakebase modules not available.")
elif not instance_exists:
    print(f"Creating Lakebase instance '{LAKEBASE_INSTANCE_NAME}'...")
    print("⏳ This may take 5-10 minutes...")
    
    instance = DatabaseInstance(
        name=LAKEBASE_INSTANCE_NAME,
        capacity="CU_1",  # Start with smallest capacity
        node_count=1,
        enable_readable_secondaries=False,
        retention_window_in_days=7,
    )
    
    try:
        instance_create = w.database.create_database_instance_and_wait(instance)
        print(f"✓ Instance created successfully!")
        print(f"  Name: {instance_create.name}")
        print(f"  Status: {instance_create.status}")
        print(f"  DNS: {instance_create.read_write_dns}")
    except Exception as e:
        print(f"✗ Error creating instance: {e}")
        print("\n⚠️ If you see permission errors, try creating via the UI:")
        print("  1. Go to Compute > Lakebase in your Databricks workspace")
        print("  2. Click 'Create Instance'")
        print(f"  3. Name: {LAKEBASE_INSTANCE_NAME}")
        print("  4. Capacity: CU_1")
else:
    print("Skipping instance creation (already exists)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8d. Create Superuser Role

# COMMAND ----------

# Create superuser role for current user
if not LAKEBASE_AVAILABLE:
    print("⚠️ Skipping - Lakebase modules not available.")
else:
    try:
        superuser_role = DatabaseInstanceRole(
            name=current_user.user_name,
            identity_type=DatabaseInstanceRoleIdentityType.USER,
            membership_role=DatabaseInstanceRoleMembershipRole.DATABRICKS_SUPERUSER,
            attributes=DatabaseInstanceRoleAttributes(
                bypassrls=True,
                createdb=True,
                createrole=True
            ),
        )
        
        w.database.create_database_instance_role(
            instance_name=LAKEBASE_INSTANCE_NAME,
            database_instance_role=superuser_role,
        )
        print(f"✓ Created superuser role for: {current_user.user_name}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"✓ Superuser role already exists for: {current_user.user_name}")
        else:
            print(f"⚠ Could not create superuser role: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8e. Create Database Catalog

# COMMAND ----------

# Create the Lakebase catalog (connects Lakebase to Unity Catalog)
if not LAKEBASE_AVAILABLE:
    print("⚠️ Skipping - Lakebase modules not available.")
else:
    try:
        catalog = DatabaseCatalog(
            name=LAKEBASE_PG_CATALOG,
            database_instance_name=LAKEBASE_INSTANCE_NAME,
            database_name=LAKEBASE_DATABASE_NAME,
            create_database_if_not_exists=True,
        )
        
        catalog_create = w.database.create_database_catalog(catalog)
        print(f"✓ Created Lakebase catalog: {catalog_create.name}")
        print(f"  Database: {LAKEBASE_DATABASE_NAME}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"✓ Catalog '{LAKEBASE_PG_CATALOG}' already exists")
        else:
            print(f"⚠ Error creating catalog: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8f. Create Synced Tables
# MAGIC 
# MAGIC Sync your Delta tables to Lakebase for real-time PostgreSQL access.

# COMMAND ----------

# Define tables to sync from Delta to Lakebase
TABLES_TO_SYNC = [
    {
        "source": f"{CATALOG_NAME}.{SCHEMA_NAME}.stores",
        "target": "stores_synced",
        "primary_key": ["store_id"],
    },
    {
        "source": f"{CATALOG_NAME}.{SCHEMA_NAME}.stores_kpi_view",
        "target": "stores_kpi_synced",
        "primary_key": ["store_id"],
    },
    {
        "source": f"{CATALOG_NAME}.{SCHEMA_NAME}.pos_transactions",
        "target": "transactions_synced",
        "primary_key": ["txn_id"],
        "timeseries_key": "timestamp",
    },
    {
        "source": f"{CATALOG_NAME}.{SCHEMA_NAME}.inventory_levels",
        "target": "inventory_synced",
        "primary_key": ["store_id", "ingredient_id"],
    },
    {
        "source": f"{CATALOG_NAME}.{SCHEMA_NAME}.employees",
        "target": "employees_synced",
        "primary_key": ["employee_id"],
    },
    {
        "source": f"{CATALOG_NAME}.{SCHEMA_NAME}.labor_schedule",
        "target": "labor_schedule_synced",
        "primary_key": ["store_id", "date", "hour"],
    },
]

print(f"Will sync {len(TABLES_TO_SYNC)} tables to Lakebase:")
for table in TABLES_TO_SYNC:
    print(f"  • {table['source']} → {table['target']}")

# COMMAND ----------

# Create synced tables
synced_results = []

if not LAKEBASE_AVAILABLE:
    print("⚠️ Skipping - Lakebase modules not available.")
else:
    new_pipeline = NewPipelineSpec(
        storage_catalog=CATALOG_NAME,
        storage_schema=SCHEMA_NAME,
    )

    for table_config in TABLES_TO_SYNC:
        source_table = table_config["source"]
        target_name = table_config["target"]
        primary_key = table_config["primary_key"]
        timeseries_key = table_config.get("timeseries_key")
        
        print(f"\n📊 Syncing: {source_table}")
        
        try:
            spec = SyncedTableSpec(
                source_table_full_name=source_table,
                primary_key_columns=primary_key,
                timeseries_key=timeseries_key,
                create_database_objects_if_missing=True,
                new_pipeline_spec=new_pipeline,
                scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
            )
            
            synced_table = SyncedDatabaseTable(
                name=f"{LAKEBASE_PG_CATALOG}.public.{target_name}",
                database_instance_name=LAKEBASE_INSTANCE_NAME,
                logical_database_name=LAKEBASE_DATABASE_NAME,
                spec=spec,
            )
            
            result = w.database.create_synced_database_table(synced_table)
            print(f"  ✓ Created synced table: {target_name}")
            print(f"    Pipeline ID: {result.id}")
            synced_results.append({
                "table": target_name,
                "pipeline_id": result.id,
                "status": "created"
            })
            
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  ✓ Synced table '{target_name}' already exists")
                synced_results.append({
                    "table": target_name,
                    "pipeline_id": None,
                    "status": "exists"
                })
            else:
                print(f"  ✗ Error: {e}")
                synced_results.append({
                    "table": target_name,
                    "pipeline_id": None,
                    "status": f"error: {str(e)[:50]}"
                })

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8g. Lakebase Setup Summary

# COMMAND ----------

# Print summary
print("=" * 60)
print("Lakebase Setup Summary")
print("=" * 60)

if not LAKEBASE_AVAILABLE:
    print("\n⚠️ Lakebase modules not available.")
    print("   To use Lakebase:")
    print("   1. Upgrade SDK: pip install databricks-sdk>=0.60.0")
    print("   2. Restart your cluster")
    print("   3. Re-run section 8")
else:
    print(f"\nInstance: {LAKEBASE_INSTANCE_NAME}")
    print(f"Database: {LAKEBASE_DATABASE_NAME}")
    print(f"Catalog: {LAKEBASE_PG_CATALOG}")
    print(f"\nSynced Tables:")

    for result in synced_results:
        status_icon = "✓" if result["status"] in ["created", "exists"] else "✗"
        print(f"  {status_icon} {result['table']}: {result['status']}")
        if result["pipeline_id"]:
            workspace_url = w.config.host
            print(f"      Pipeline: {workspace_url}/pipelines/{result['pipeline_id']}")

    print("\n" + "=" * 60)
    print("Connection Info:")
    print("=" * 60)
    try:
        instance_info = w.database.get_database_instance(name=LAKEBASE_INSTANCE_NAME)
        print(f"  Host: {instance_info.read_write_dns}")
        print(f"  Port: 5432")
        print(f"  Database: {LAKEBASE_DATABASE_NAME}")
        print(f"\n  Connection string:")
        print(f"  postgresql://<user>:<password>@{instance_info.read_write_dns}:5432/{LAKEBASE_DATABASE_NAME}")
    except Exception as e:
        print(f"  Could not retrieve connection info: {e}")

    print("\n⚠️ Remember: Lakebase instances incur ongoing costs!")
    print("   Delete via Compute > Lakebase when no longer needed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Summary

# COMMAND ----------

# Print summary of created tables
print("=" * 60)
print("StoreSight IQ - Data Generation Complete!")
print("=" * 60)
print(f"\nCatalog: {CATALOG_NAME}")
print(f"Schema: {SCHEMA_NAME}")
print("\nDelta Tables created:")

tables = spark.sql(f"SHOW TABLES IN {CATALOG_NAME}.{SCHEMA_NAME}").collect()
for table in tables:
    try:
        count = spark.sql(f"SELECT COUNT(*) as cnt FROM {CATALOG_NAME}.{SCHEMA_NAME}.{table.tableName}").first().cnt
        print(f"  • {table.tableName}: {count:,} rows")
    except:
        print(f"  • {table.tableName}: (view)")

print(f"\nLakebase Instance: {LAKEBASE_INSTANCE_NAME}")
print(f"Lakebase Database: {LAKEBASE_DATABASE_NAME}")

print("\n" + "=" * 60)
print("Next steps:")
print("  1. Run notebook 02_train_demand_forecast_model.py")
print("  2. Run notebook 03_train_labor_optimization_model.py")
print("  3. Run notebook 04_train_inventory_prediction_model.py")
print("  4. Run notebook 05_train_prep_schedule_model.py")
print("  5. Run notebook 06_setup_genie_space.py")
print("  6. Run notebook 07_setup_streaming_job.py")
print("=" * 60)


