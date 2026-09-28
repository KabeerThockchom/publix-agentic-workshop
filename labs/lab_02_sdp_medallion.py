# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 2 - Medallion Pipeline with Spark Declarative Pipelines
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** turn raw Zerobus events into a clean, queryable semantic layer for Genie. ~30 minutes.
# MAGIC
# MAGIC You will build the silver and gold layers of a medallion architecture using Spark Declarative
# MAGIC Pipelines (SDP). SDP is serverless streaming orchestration - write SQL, Databricks runs it with
# MAGIC managed checkpointing and fault tolerance. Great fit if your team already thinks in SQL.

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
# MAGIC Your first job is to build a streaming table that:
# MAGIC - Reads bronze.sales_events as a stream
# MAGIC - Types columns: timestamp, numeric amounts, quantities
# MAGIC - Drops rows with missing event_id or item_id (quality gate)
# MAGIC - Clusters by store_number and item_id for query performance
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Build a streaming table called silver_sales in publix_agentic_workshop.medallion
# MAGIC > that reads from bronze.sales_events and:
# MAGIC > - Casts event_timestamp to TIMESTAMP
# MAGIC > - Casts quantity_sold to INT
# MAGIC > - Casts unit_price to DECIMAL(10, 2)
# MAGIC > - Casts total_amount to DECIMAL(12, 2)
# MAGIC > - Includes a constraint that drops rows where event_id or item_id is null
# MAGIC > - Uses liquid clustering on store_number and item_id
# MAGIC > Write it as a CREATE OR REFRESH STREAMING TABLE statement.
# MAGIC > ```
# MAGIC
# MAGIC Genie Code will write the SQL. Review it against the reference below, then save it
# MAGIC to `src/pipelines/transformations/silver_sales.sql` in your repo.

# COMMAND ----------

# reference solution - actual silver layer
spark.sql("""
CREATE OR REFRESH STREAMING TABLE silver_sales
  (CONSTRAINT valid_event EXPECT (event_id IS NOT NULL AND item_id IS NOT NULL) ON VIOLATION DROP ROW)
  COMMENT "Cleaned, typed Publix sales events."
  CLUSTER BY (store_number, item_id)
AS
SELECT
  event_id,
  store_number,
  CAST(event_timestamp AS TIMESTAMP)        AS event_ts,
  item_id,
  item_name,
  item_category,
  CAST(quantity_sold AS INT)            AS quantity_sold,
  CAST(unit_price AS DECIMAL(10, 2))    AS unit_price,
  CAST(total_amount AS DECIMAL(12, 2))  AS total_amount,
  cashier_id,
  transaction_id
FROM STREAM(bronze.sales_events)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Layer 2: Gold (business semantics)
# MAGIC
# MAGIC Next, build a materialized view that aggregates silver to daily sales by store and item.
# MAGIC This is your Genie-ready semantic layer. Genie will ask questions against this table.
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Build a materialized view called gold_store_item_daily in the medallion schema
# MAGIC > that aggregates silver_sales to daily units sold, revenue, and line item counts
# MAGIC > grouped by store_number, item_id, item_name, item_category, and sales_date.
# MAGIC > Include SUM(quantity_sold) as units_sold, SUM(total_amount) as revenue,
# MAGIC > and COUNT(*) as line_items. Cast the date from event_ts. Write it as
# MAGIC > CREATE OR REFRESH MATERIALIZED VIEW.
# MAGIC > ```
# MAGIC
# MAGIC Save this to `src/pipelines/transformations/gold_store_item_daily.sql`.

# COMMAND ----------

# reference solution - actual gold layer
spark.sql("""
CREATE OR REFRESH MATERIALIZED VIEW gold_store_item_daily
  COMMENT "Daily units and revenue by store and item."
AS
SELECT
  store_number,
  item_id,
  item_name,
  item_category,
  CAST(event_ts AS DATE)  AS sales_date,
  SUM(quantity_sold)      AS units_sold,
  SUM(total_amount)       AS revenue,
  COUNT(*)                AS line_items
FROM silver_sales
GROUP BY store_number, item_id, item_name, item_category, CAST(event_ts AS DATE)
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
# MAGIC > schema medallion, with serverless: true, and references the two SQL files:
# MAGIC > ../src/pipelines/transformations/silver_sales.sql and
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

# reference - the DAB resources block for this pipeline
# (shown for context; you may have customized variables)

resources:
  pipelines:
    medallion:
      name: "[${bundle.target}] publix-medallion"
      catalog: ${var.catalog}
      schema: medallion
      serverless: true
      channel: CURRENT
      libraries:
        - file:
            path: ../src/pipelines/transformations/silver_sales.sql
        - file:
            path: ../src/pipelines/transformations/gold_store_item_daily.sql

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
spark.sql("SELECT COUNT(*) as bronze_count FROM publix_agentic_workshop.bronze.sales_events").show(truncate=False)
spark.sql("SELECT COUNT(*) as silver_count FROM publix_agentic_workshop.medallion.silver_sales").show(truncate=False)
spark.sql("SELECT COUNT(*) as gold_count FROM publix_agentic_workshop.medallion.gold_store_item_daily").show(truncate=False)

# COMMAND ----------

# sample data: see what silver_sales looks like
spark.sql("""
SELECT
  event_id, store_number, event_ts, item_id, item_name,
  quantity_sold, unit_price, total_amount
FROM publix_agentic_workshop.medallion.silver_sales
LIMIT 5
""").display()

# COMMAND ----------

# sample data: daily aggregation (gold layer)
spark.sql("""
SELECT
  store_number, item_id, item_name, sales_date,
  units_sold, revenue, line_items
FROM publix_agentic_workshop.medallion.gold_store_item_daily
ORDER BY sales_date DESC, revenue DESC
LIMIT 10
""").display()

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
# MAGIC - Your constraint `EXPECT (event_id IS NOT NULL AND item_id IS NOT NULL) ON VIOLATION DROP ROW`
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
# MAGIC ## Next: Lab 3
# MAGIC
# MAGIC Your medallion is ready. In Lab 3, you will:
# MAGIC - Create a Genie space indexed on gold_store_item_daily
# MAGIC - Ask Genie questions like "sales by region" or "top items by revenue"
# MAGIC - See how Genie uses your semantic layer to generate queries automatically
# MAGIC
# MAGIC The whole loop: Zerobus (Lab 1) > Medallion (Lab 2, today) > Genie (Lab 3) > App (Lab 4).
