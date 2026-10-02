-- Silver: POSA Sales
-- Parses Kafka envelope, explodes BasketItems to line-item facts.
-- One row per item sold (line item), with store, transaction, product, and value data.

CREATE OR REFRESH STREAMING TABLE silver_pos_sales
  (CONSTRAINT valid_transaction EXPECT (value.Basket.TransactionId IS NOT NULL AND item_sku IS NOT NULL) ON VIOLATION DROP ROW)
  COMMENT "Cleaned POSA sales line items, one row per item sold."
  CLUSTER BY (store_number, item_sku)
AS
SELECT
  -- Kafka envelope metadata
  partition,
  offset,
  CAST(FROM_UNIXTIME(timestamp / 1000) AS TIMESTAMP) AS kafka_ts,
  key,
  -- Transaction metadata
  value.TicketNumber AS ticket_number,
  value.TransactionDateTime AS transaction_datetime,
  value.Basket.TransactionId AS transaction_id,
  value.Basket.StoreNumber AS store_number,
  value.Basket.LaneNumber AS lane_number,
  CAST(value.Basket.StartTime AS TIMESTAMP) AS start_time,
  CAST(value.Basket.EndTime AS TIMESTAMP) AS end_time,
  -- Line item (exploded from BasketItems array)
  item.Sku AS item_sku,
  item.Gtin AS item_gtin,
  item.Name AS item_name,
  item.FamilyGroup AS item_family,
  item.SubDepartmentId AS item_dept_id,
  CAST(item.Quantity AS INT) AS quantity,
  CAST(item.UnitPrice AS DECIMAL(10, 2)) AS unit_price,
  CAST(item.TotalPrice AS DECIMAL(12, 2)) AS total_price,
  item.IsRefundItem,
  item.IsMerchandise,
  -- Transaction totals (same for all items in this transaction)
  CAST(value.Basket.Subtotal AS DECIMAL(12, 2)) AS txn_subtotal,
  CAST(value.Basket.TaxTotal AS DECIMAL(10, 2)) AS txn_tax,
  CAST(value.Basket.Total AS DECIMAL(12, 2)) AS txn_total,
  CAST(value.Basket.Savings AS DECIMAL(10, 2)) AS txn_savings,
  -- Cashier info (first from array)
  value.Basket.CashierDetails[0].Username AS cashier_username,
  value.Basket.CashierDetails[0].Name AS cashier_name
FROM STREAM(bronze.pos_sales_raw)
-- Explode each line item in the basket
LATERAL VIEW EXPLODE(value.Basket.BasketItems) exploded_items AS item
