-- Publix Agentic Workshop - Per-User Catalogs, Schemas, and Zerobus Landing Tables (Reference DDL)
-- ================================================================================================
-- This is the reference DDL. Notebook 1 creates a per-user catalog via the my_name widget.
--
-- Each workshop participant creates their OWN catalog: `publix_agentic_<yourname>`.
-- Replace `publix_agentic_workshop` below with your own `publix_agentic_<yourname>` (you all share one workspace).
-- Everyone builds the same medallion structure (bronze -> silver -> gold) in their own catalog.
--
-- This file is the reference schema definition; Notebook 1 creates it per-user via the my_name widget.

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
