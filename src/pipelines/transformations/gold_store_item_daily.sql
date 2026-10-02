-- Gold: Daily Sales by Store and Item
-- Aggregates silver_pos_sales to daily units, revenue, and transaction counts.
-- One row per store-item-date combination.

CREATE OR REFRESH MATERIALIZED VIEW gold_store_item_daily
  COMMENT "Daily sales by store, item, and date. Aggregated from POSA line items."
AS
SELECT
  store_number,
  item_sku,
  item_gtin,
  item_name,
  item_family,
  CAST(start_time AS DATE) AS sales_date,
  COUNT(DISTINCT transaction_id) AS num_transactions,
  SUM(quantity) AS units_sold,
  SUM(total_price) AS revenue,
  COUNT(*) AS line_item_count,
  MIN(unit_price) AS min_unit_price,
  MAX(unit_price) AS max_unit_price,
  AVG(unit_price) AS avg_unit_price
FROM silver_pos_sales
GROUP BY
  store_number,
  item_sku,
  item_gtin,
  item_name,
  item_family,
  CAST(start_time AS DATE)
