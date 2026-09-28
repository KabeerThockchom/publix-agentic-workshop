-- Lab 2 - Gold: daily sales by store and item, for the semantic layer + Genie.
-- Materialized view over silver_sales (same pipeline target schema, unqualified name).

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
GROUP BY store_number, item_id, item_name, item_category, CAST(event_ts AS DATE);
