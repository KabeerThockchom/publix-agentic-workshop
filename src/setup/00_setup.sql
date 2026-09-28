-- Publix Agentic Workshop - catalog, schemas, and Zerobus landing tables.
-- Run once against the workshop workspace before Lab 1.
-- The two bronze tables are the Zerobus ingest targets; SDP reads them downstream.

CREATE CATALOG IF NOT EXISTS publix_agentic_workshop;
CREATE SCHEMA  IF NOT EXISTS publix_agentic_workshop.bronze;
CREATE SCHEMA  IF NOT EXISTS publix_agentic_workshop.medallion;

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
