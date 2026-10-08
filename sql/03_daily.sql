CREATE OR REPLACE TABLE daily_sales AS
SELECT
    strftime(order_ts, '%Y-%m-%d') AS order_date,
    COUNT(*) AS orders,
    CAST(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS BIGINT) AS cancelled,
    ROUND(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 2) AS revenue
FROM clean_orders
GROUP BY 1
ORDER BY 1;