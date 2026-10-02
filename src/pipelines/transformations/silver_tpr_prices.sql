-- Silver: TPR Price Updates
-- Parses Kafka envelope, base64-decodes price and date fields.
-- One row per price event with store, item, and effective pricing.

CREATE OR REFRESH STREAMING TABLE silver_tpr_prices
  (CONSTRAINT valid_price EXPECT (event_id IS NOT NULL AND item_code IS NOT NULL) ON VIOLATION DROP ROW)
  COMMENT "Cleaned TPR price events with base64-decoded fields."
  CLUSTER BY (store_number, item_code)
AS
SELECT
  -- Kafka envelope metadata
  partition,
  offset,
  CAST(FROM_UNIXTIME(timestamp / 1000) AS TIMESTAMP) AS kafka_ts,
  key,
  -- Event metadata
  data.SystemId AS system_id,
  data.EventType AS event_type,
  data.Event_Id AS event_id,
  CAST(CAST(UNBASE64(data.Event_Timestamp) AS STRING) AS TIMESTAMP) AS event_timestamp,
  -- Item and store
  data.Item_Code AS item_code,
  data.Store_Number AS store_number,
  -- Pricing type and action
  data.Price_Type AS price_type,
  data.EventAction AS event_action,
  -- Dates (base64-decoded)
  CAST(CAST(UNBASE64(data.Effective_Date) AS STRING) AS DATE) AS effective_date,
  CAST(CAST(UNBASE64(data.Term_Date) AS STRING) AS DATE) AS term_date,
  -- Prices (base64-decoded and cast to decimal)
  CAST(CAST(UNBASE64(data.Selling_Price) AS STRING) AS DECIMAL(10, 2)) AS selling_price,
  CAST(CAST(UNBASE64(data.Deal_Price) AS STRING) AS DECIMAL(10, 2)) AS deal_price,
  CAST(CAST(UNBASE64(data.Break_Retail_Price) AS STRING) AS DECIMAL(10, 2)) AS break_retail_price,
  -- Quantities
  CAST(data.Sale_Quantity AS INT) AS sale_quantity,
  CAST(data.Deal_Quantity AS INT) AS deal_quantity,
  -- Additional attributes
  data.Mix_Match_Code AS mix_match_code,
  data.Vendor_Number AS vendor_number,
  data.Created_By AS created_by,
  CAST(CAST(UNBASE64(data.Created_On) AS STRING) AS TIMESTAMP) AS created_on
FROM STREAM(bronze.price_updates_raw)
