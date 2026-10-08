CREATE OR REPLACE TABLE clean_orders AS
SELECT DISTINCT ON (order_id) *
FROM raw_orders
WHERE customer_id IS NOT NULL
  AND amount > 0
ORDER BY order_id;