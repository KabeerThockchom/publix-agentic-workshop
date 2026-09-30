-- Publix Agentic Workshop - Shared catalog, schemas, and Zerobus landing tables
-- =============================================================================
-- Run once against the workshop workspace before Lab 1.
--
-- This setup creates a shared catalog (`publix_agentic_workshop`) where all workshop
-- participants will populate the same gold table (`medallion.gold_store_item_daily`).
-- Everyone uses the same bronze landing tables (populated by Zerobus in Lab 1),
-- and everyone builds silver and gold through the SDP pipeline in Lab 2.
--
-- Lab 3 queries the shared gold table together. Lab 4 builds an app on top of it.

CREATE CATALOG IF NOT EXISTS publix_agentic_workshop;
CREATE SCHEMA  IF NOT EXISTS publix_agentic_workshop.bronze   COMMENT "Raw Zerobus ingest landing tables";
CREATE SCHEMA  IF NOT EXISTS publix_agentic_workshop.medallion COMMENT "Silver (streaming) + Gold (materialized) shared outputs";

-- Sales events (Lab 1 Zerobus target). Timestamps land as ISO strings; cast in silver.
CREATE TABLE IF NOT EXISTS publix_agentic_workshop.bronze.sales_events (
  event_id        STRING,
  store_number    INT,
  event_timestamp     STRING,
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
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

-- Item price updates (Lab 1 Zerobus target).
CREATE TABLE IF NOT EXISTS publix_agentic_workshop.bronze.price_updates (
  event_id        STRING,
  event_timestamp     STRING,
  item_id         INT,
  item_name       STRING,
  old_price       DOUBLE,
  new_price       DOUBLE,
  effective_date  STRING,
  ingestion_time  STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
