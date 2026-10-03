# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 4 - Medallion Pipeline with Spark Declarative Pipelines
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** This is the main hands-on exercise. Build silver + gold layers in your own catalog.
# MAGIC ~30 minutes.
# MAGIC
# MAGIC You will build the silver and gold layers of a medallion architecture using Spark Declarative
# MAGIC Pipelines (SDP). SDP is serverless streaming orchestration - write SQL, Databricks runs it with
# MAGIC managed checkpointing and fault tolerance.
# MAGIC
# MAGIC **Per-user exercise:** By the end of this notebook, you will have built a complete medallion pipeline
# MAGIC in your own catalog: `publix_agentic_<yourname>.medallion.gold_store_item_daily`. Everyone builds
# MAGIC the same structure, each in their own space - compare results with your neighbor at the end!

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
# MAGIC ## Why medallion? Why SDP?
# MAGIC
# MAGIC **Medallion** is the industry standard for lakehouse design:
# MAGIC - **Bronze** - raw ingest (populated by Lab 1 Zerobus)
# MAGIC - **Silver** - cleaned, typed, quality-checked facts (streaming table)
# MAGIC - **Gold** - aggregated business semantics (materialized views)
# MAGIC
# MAGIC **Spark Declarative Pipelines** is a managed service for SQL-first teams:
# MAGIC - You write SQL DDL (CREATE STREAMING TABLE, CREATE MATERIALIZED VIEW)
# MAGIC - Databricks handles streaming orchestration, checkpoints, retries, and state
# MAGIC - Serverless execution means no cluster management
# MAGIC - Great for teams that don't want to hand-roll Spark streaming code
# MAGIC - Best for data that is relatively clean at source (like Zerobus)
# MAGIC
# MAGIC Today you will build both layers using SDP. Tomorrow you will put Genie on top of gold.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Layer 1: Silver (cleaned, typed facts)
# MAGIC
# MAGIC Your first job is to build TWO streaming tables:
# MAGIC
# MAGIC ### silver_pos_sales
# MAGIC - Reads bronze.pos_sales_raw as a stream (Kafka envelope with nested Basket)
# MAGIC - Explodes BasketItems array to one row per line item
# MAGIC - Extracts store, transaction, and item details from the nested structure
# MAGIC - Drops rows with missing SKU or quantity (quality gate)
# MAGIC - Clusters by store_number and item_sku for query performance
# MAGIC
# MAGIC ### silver_tpr_prices
# MAGIC - Reads bronze.price_updates_raw as a stream (Kafka envelope with base64 fields)
# MAGIC - Base64-decodes the Selling_Price and Effective_Date fields
# MAGIC - Types fields as appropriate (timestamp, decimal for price)
# MAGIC - Clusters by store_number and item_code
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Build a streaming table called silver_pos_sales in publix_agentic_<yourname>.medallion that:
# MAGIC > - Reads from STREAM(bronze.pos_sales_raw)
# MAGIC > - Explodes value.Basket.BasketItems to one row per line item
# MAGIC > - Extracts: store_number (value.Basket.StoreNumber), transaction_id (value.Basket.TransactionId),
# MAGIC >   start_time (CAST(value.Basket.StartTime to TIMESTAMP)), item_sku (Sku), item_gtin (Gtin),
# MAGIC >   item_name (Name), item_family (FamilyGroup), quantity (Quantity), unit_price (UnitPrice),
# MAGIC >   total_price (TotalPrice)
# MAGIC > - Includes EXPECT (transaction_id IS NOT NULL AND item_sku IS NOT NULL) ON VIOLATION DROP ROW
# MAGIC > - Uses CLUSTER BY (store_number, item_sku)
# MAGIC > Write it as a CREATE OR REFRESH STREAMING TABLE statement.
# MAGIC > ```
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code** (for silver_tpr_prices)
# MAGIC > ```
# MAGIC > Build a streaming table called silver_tpr_prices in publix_agentic_<yourname>.medallion that:
# MAGIC > - Reads from STREAM(bronze.price_updates_raw)
# MAGIC > - Base64-decodes: data.Selling_Price, data.Effective_Date, data.Term_Date, data.Deal_Price
# MAGIC > - Extracts: event_id (data.Event_Id), item_code (data.Item_Code), store_number (data.Store_Number),
# MAGIC >   event_timestamp (CAST(UNBASE64(data.Event_Timestamp) AS STRING AS TIMESTAMP)), price_type (data.Price_Type),
# MAGIC >   selling_price (CAST(decoded AS DECIMAL(10,2))), deal_price (CAST(decoded AS DECIMAL(10,2))),
# MAGIC >   effective_date (CAST(decoded AS DATE))
# MAGIC > - Includes EXPECT (event_id IS NOT NULL AND item_code IS NOT NULL) ON VIOLATION DROP ROW
# MAGIC > - Uses CLUSTER BY (store_number, item_code)
# MAGIC > Write it as a CREATE OR REFRESH STREAMING TABLE statement.
# MAGIC > ```
# MAGIC
# MAGIC Genie Code will write the SQL. Review it against the reference below, then save them
# MAGIC to `src/pipelines/transformations/silver_pos_sales.sql` and `silver_tpr_prices.sql` in your repo.

# COMMAND ----------

# reference solution - silver_pos_sales layer (explodes nested Basket.BasketItems)
spark.sql(f"""
CREATE OR REFRESH STREAMING TABLE {CATALOG}.medallion.silver_pos_sales
  (CONSTRAINT valid_transaction EXPECT (transaction_id IS NOT NULL AND item_sku IS NOT NULL) ON VIOLATION DROP ROW)
  COMMENT "Cleaned, typed POSA sales line items (one row per basket item)."
  CLUSTER BY (store_number, item_sku)
AS
SELECT
  value.Basket.StoreNumber             AS store_number,
  value.Basket.TransactionId           AS transaction_id,
  CAST(value.Basket.StartTime AS TIMESTAMP) AS start_time,
  item.Sku                             AS item_sku,
  item.Gtin                            AS item_gtin,
  item.Name                            AS item_name,
  item.FamilyGroup                     AS item_family,
  CAST(item.Quantity AS INT)           AS quantity,
  CAST(item.UnitPrice AS DECIMAL(10, 2))  AS unit_price,
  CAST(item.TotalPrice AS DECIMAL(12, 2)) AS total_price
FROM STREAM({CATALOG}.bronze.pos_sales_raw)
LATERAL VIEW EXPLODE(value.Basket.BasketItems) exploded AS item
""")

# reference solution - silver_tpr_prices layer (base64-decodes and types)
spark.sql(f"""
CREATE OR REFRESH STREAMING TABLE {CATALOG}.medallion.silver_tpr_prices
  (CONSTRAINT valid_price EXPECT (event_id IS NOT NULL AND item_code IS NOT NULL) ON VIOLATION DROP ROW)
  COMMENT "Cleaned, typed TPR price events with base64-decoded fields."
  CLUSTER BY (store_number, item_code)
AS
SELECT
  data.Event_Id                        AS event_id,
  data.Item_Code                       AS item_code,
  data.Store_Number                    AS store_number,
  data.Price_Type                      AS price_type,
  CAST(CAST(UNBASE64(data.Event_Timestamp) AS STRING) AS TIMESTAMP) AS event_timestamp,
  CAST(CAST(UNBASE64(data.Effective_Date) AS STRING) AS DATE)       AS effective_date,
  CAST(CAST(UNBASE64(data.Term_Date) AS STRING) AS DATE)            AS term_date,
  CAST(CAST(UNBASE64(data.Selling_Price) AS STRING) AS DECIMAL(10, 2)) AS selling_price,
  CAST(CAST(UNBASE64(data.Deal_Price) AS STRING) AS DECIMAL(10, 2))    AS deal_price
FROM STREAM({CATALOG}.bronze.price_updates_raw)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Layer 2: Gold (business semantics)
# MAGIC
# MAGIC Next, build a materialized view that aggregates silver_pos_sales to daily units and revenue
# MAGIC by store and item. This is your Genie-ready semantic layer. (Price lives in silver_tpr_prices;
# MAGIC you weave it in at analysis time - EDA and the forecast model - rather than baking it into gold.)
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Build a materialized view called gold_store_item_daily in the medallion schema that:
# MAGIC > - Aggregates silver_pos_sales by store_number, item_sku, item_gtin, item_name, item_family,
# MAGIC >   and sales_date (CAST(start_time AS DATE))
# MAGIC > - Computes: COUNT(DISTINCT transaction_id) as num_transactions, SUM(quantity) as units_sold,
# MAGIC >   SUM(total_price) as revenue, COUNT(*) as line_item_count,
# MAGIC >   MIN/MAX/AVG(unit_price) as min_unit_price / max_unit_price / avg_unit_price
# MAGIC > - Write it as CREATE OR REFRESH MATERIALIZED VIEW.
# MAGIC > ```
# MAGIC
# MAGIC Save this to `src/pipelines/transformations/gold_store_item_daily.sql`.

# COMMAND ----------

# reference solution - gold layer (daily store-item aggregation from POSA line items)
spark.sql(f"""
CREATE OR REFRESH MATERIALIZED VIEW {CATALOG}.medallion.gold_store_item_daily
  COMMENT "Daily sales by store, item, and date. Aggregated from POSA line items."
AS
SELECT
  store_number,
  item_sku,
  item_gtin,
  item_name,
  item_family,
  CAST(start_time AS DATE)        AS sales_date,
  COUNT(DISTINCT transaction_id)  AS num_transactions,
  SUM(quantity)                   AS units_sold,
  SUM(total_price)                AS revenue,
  COUNT(*)                        AS line_item_count,
  MIN(unit_price)                 AS min_unit_price,
  MAX(unit_price)                 AS max_unit_price,
  AVG(unit_price)                 AS avg_unit_price
FROM {CATALOG}.medallion.silver_pos_sales
GROUP BY
  store_number, item_sku, item_gtin, item_name, item_family, CAST(start_time AS DATE)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Assemble and deploy the pipeline
# MAGIC
# MAGIC You now have two SQL files. Your Databricks Asset Bundle (DAB) will wire them together
# MAGIC and deploy them as a single SDP pipeline.
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Show me the resources section of a Databricks Asset Bundle for a Spark Declarative
# MAGIC > Pipeline named "publix-medallion" that targets catalog publix_agentic_workshop and
# MAGIC > schema medallion, with serverless: true, and references the three SQL files:
# MAGIC > ../src/pipelines/transformations/silver_pos_sales.sql,
# MAGIC > ../src/pipelines/transformations/silver_tpr_prices.sql, and
# MAGIC > ../src/pipelines/transformations/gold_store_item_daily.sql
# MAGIC > ```
# MAGIC
# MAGIC Look for a resources block in your repo's `resources/medallion.pipeline.yml`
# MAGIC (or ask Genie Code to show you an example DAB config).
# MAGIC
# MAGIC Once you have the SQL files and the DAB updated, deploy with:
# MAGIC ```
# MAGIC databricks bundle deploy --target dev
# MAGIC ```
# MAGIC
# MAGIC Or use the Pipelines UI: Workflows > Pipelines, click Create, and point it at your
# MAGIC SQL files. Either way, SDP will orchestrate the silver and gold tables end-to-end.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Reference - the DAB resources block for this pipeline
# MAGIC (shown for context; you may have customized variables)
# MAGIC
# MAGIC ```yaml
# MAGIC resources:
# MAGIC   pipelines:
# MAGIC     medallion:
# MAGIC       name: "[${bundle.target}] publix-medallion"
# MAGIC       catalog: ${var.catalog}
# MAGIC       schema: medallion
# MAGIC       serverless: true
# MAGIC       channel: CURRENT
# MAGIC       libraries:
# MAGIC         - file:
# MAGIC             path: ../src/pipelines/transformations/silver_pos_sales.sql
# MAGIC         - file:
# MAGIC             path: ../src/pipelines/transformations/silver_tpr_prices.sql
# MAGIC         - file:
# MAGIC             path: ../src/pipelines/transformations/gold_store_item_daily.sql
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the pipeline and validate
# MAGIC
# MAGIC Once deployed, SDP will run the pipeline on a schedule (or on-demand). To validate:
# MAGIC - Start the pipeline in the Pipelines UI
# MAGIC - Wait for both tables to compute
# MAGIC - Run the queries below to verify row counts and sample data

# COMMAND ----------

# check row counts at each layer
print("=== Medallion pipeline row counts ===")
spark.sql(f"SELECT COUNT(*) as bronze_posa_count FROM {CATALOG}.bronze.pos_sales_raw").show(truncate=False)
spark.sql(f"SELECT COUNT(*) as bronze_tpr_count FROM {CATALOG}.bronze.price_updates_raw").show(truncate=False)
spark.sql(f"SELECT COUNT(*) as silver_pos_count FROM {CATALOG}.medallion.silver_pos_sales").show(truncate=False)
spark.sql(f"SELECT COUNT(*) as silver_tpr_count FROM {CATALOG}.medallion.silver_tpr_prices").show(truncate=False)
spark.sql(f"SELECT COUNT(*) as gold_count FROM {CATALOG}.medallion.gold_store_item_daily").show(truncate=False)

# COMMAND ----------

# sample data: see what silver_pos_sales looks like (exploded line items)
spark.sql(f"""
SELECT
  store_number, transaction_id, start_time, item_sku, item_name,
  quantity, unit_price, total_price
FROM {CATALOG}.medallion.silver_pos_sales
LIMIT 5
""").display()

# COMMAND ----------

# sample data: see what silver_tpr_prices looks like (base64-decoded)
spark.sql(f"""
SELECT
  event_id, item_code, store_number, selling_price, deal_price, price_type
FROM {CATALOG}.medallion.silver_tpr_prices
LIMIT 5
""").display()

# COMMAND ----------

# sample data: daily aggregation (gold layer with pricing)
spark.sql(f"""
SELECT
  store_number, item_sku, item_name, sales_date,
  units_sold, revenue, avg_unit_price, line_item_count
FROM {CATALOG}.medallion.gold_store_item_daily
ORDER BY sales_date DESC, revenue DESC
LIMIT 10
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Checkpoint: Compare with Your Neighbor
# MAGIC
# MAGIC Each of you built the same pipeline structure in your own catalog. Confirm your row counts
# MAGIC roughly match your neighbor's. If gold has 0 rows, ask an instructor.

# COMMAND ----------

# Quick sanity check
gold_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {CATALOG}.medallion.gold_store_item_daily").collect()[0]["cnt"]
silver_pos_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {CATALOG}.medallion.silver_pos_sales").collect()[0]["cnt"]
silver_tpr_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {CATALOG}.medallion.silver_tpr_prices").collect()[0]["cnt"]

print(f"Your pipeline status:")
print(f"  Silver POS (line items): {silver_pos_count}")
print(f"  Silver TPR (prices): {silver_tpr_count}")
print(f"  Gold rows: {gold_count}")

if gold_count == 0:
    print("\n[!] Gold table is empty. Pipeline may not have started. Check the Pipelines UI and ask an instructor.")
else:
    print(f"\n[OK] You have {gold_count} gold rows. Compare with your neighbor - you should be in the same ballpark.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Key concepts: gotchas and best practices
# MAGIC
# MAGIC **Liquid Clustering vs. Partitioning**
# MAGIC - SDP streaming tables use CLUSTER BY (liquid clustering), not PARTITION BY
# MAGIC - Liquid clustering is automatic, adaptive, and makes queries fast without manual partitions
# MAGIC - No PARTITION BY in the DDL - let Databricks choose
# MAGIC
# MAGIC **Expectations drop rows silently**
# MAGIC - Your constraint `EXPECT (transaction_id IS NOT NULL AND item_sku IS NOT NULL) ON VIOLATION DROP ROW`
# MAGIC   silently filters out bad rows. Monitor this - check the pipeline's event log if you suspect data loss
# MAGIC - Alternatively, use `ON VIOLATION FAIL PIPELINE` to alert you to bad data
# MAGIC
# MAGIC **Schema evolution requires full refresh**
# MAGIC - If upstream schema changes (e.g., a new column in bronze), you may need to `DROP` and recreate
# MAGIC   the streaming table. SDP does not auto-evolve if a column is dropped
# MAGIC - Renames and new columns are safe - old columns just get dropped
# MAGIC
# MAGIC **Materialized views compute on schedule**
# MAGIC - Gold materialized views refresh when the pipeline runs (usually daily or on trigger)
# MAGIC - Genie will query the latest gold snapshot, not live silver
# MAGIC - For sub-minute freshness, build a streaming view instead - tradeoff: queryability vs. freshness

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next: Notebook 5
# MAGIC
# MAGIC Your medallion is ready. In Notebook 5, you will:
# MAGIC - Create a Genie space indexed on gold_store_item_daily
# MAGIC - Ask Genie questions like "sales by region" or "top items by revenue"
# MAGIC - See how Genie uses your semantic layer to generate queries automatically
# MAGIC
# MAGIC The whole loop: Setup (Notebook 1) > Kafka/Zerobus (Notebooks 2-3) > Medallion (Notebook 4, now) > Genie (Notebook 5) > App (Notebook 6).
