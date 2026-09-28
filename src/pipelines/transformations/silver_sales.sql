-- Lab 2 - Silver: clean + typed Publix sales, streamed from the Zerobus bronze table.
-- Bronze is populated by the Zerobus publisher (Lab 1); we stream its appends here.
-- Partially-qualified `bronze.sales_events` resolves to the pipeline's target catalog.

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
FROM STREAM(bronze.sales_events);
