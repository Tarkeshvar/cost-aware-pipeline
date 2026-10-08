CREATE OR REPLACE TABLE raw_orders AS
SELECT * FROM read_csv_auto('{csv_path}');