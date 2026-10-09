# Cost-Aware Batch Pipeline

A batch pipeline that cleans fake e-commerce order data and builds a daily sales table. The same job is built two ways (pandas and SQL on DuckDB). Each one is measured for time and memory, and a short AI summary explains the cost and performance trade-off.

Assignment: DAI-031, DataOps.

## What it does

1. Generates synthetic order data with duplicates, missing customer ids and bad amounts on purpose.
2. Cleans the data and builds a daily table (orders, cancelled orders, revenue from completed orders).
3. Runs the job in two ways: pandas and SQL (DuckDB).
4. Measures runtime, peak memory and rows per second for each, at 100k, 1M and 5M rows.
5. Saves the measurements in a metrics table and writes a short summary with an AI model.

## Flow

```
generate_data.py -> orders.csv
                      |
          +-----------+-----------+
          |                       |
   pipeline_pandas.py     pipeline_duckdb.py (sql/01, 02, 03)
          |                       |
          +-----------+-----------+
                      |
                 benchmark.py -> metrics table (DuckDB) + docs/metrics.csv
                      |
                 ai_summary.py -> docs/summary.md
```

## Folder structure

```
src/        pipeline code, benchmark, AI summary
sql/        SQL for the DuckDB version
tests/      pytest tests
data/       sample_orders.csv (small sample); big files are generated locally
docs/       metrics.csv, summary.md, design note
```

## Setup

Python 3.10 or newer.

```
git clone https://github.com/Tarkeshvar/cost-aware-pipeline.git
cd cost-aware-pipeline
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

On Mac or Linux, activate with `source venv/bin/activate`.

## How to run

```
python src/generate_data.py --rows 100000 --out data/orders.csv
python src/compare.py data/orders.csv
python src/benchmark.py --sizes 100000 1000000 5000000 --repeats 3
python src/ai_summary.py
python -m pytest tests -v
```

`compare.py` checks that both versions give the same output. The full benchmark takes a few minutes and needs about 2 GB of free memory for the 5M size.

## Cleaning rules

A row is removed if:

- `customer_id` is missing
- `amount` is 0 or less
- `order_id` is a duplicate (the first one is kept)

## Data model

- `raw_orders`: the CSV as it is
- `clean_orders`: after the cleaning rules
- `daily_sales`: one row per day with `orders`, `cancelled`, `revenue`
- `metrics`: one row per benchmark run (implementation, input rows, clean rows, seconds, peak memory, rows per second)

## Results

Middle value of 3 runs on my Windows laptop. Your numbers will be different.

| Rows  | pandas time | DuckDB time | pandas memory | DuckDB memory |
| ----- | ----------- | ----------- | ------------- | ------------- |
| 102k  | 0.29 s      | 0.28 s      | 119 MB        | 132 MB        |
| 1.02M | 2.60 s      | 0.46 s      | 245 MB        | 329 MB        |
| 5.1M  | 13.17 s     | 1.36 s      | 874 MB        | 1203 MB       |

Raw runs are in `docs/metrics.csv`.

## Trade-off

- On small data both are about the same.
- As data grows, DuckDB gets much faster: about 5.7x at 1M rows and 9.7x at 5M rows.
- DuckDB uses about 35 to 38 percent more memory at the bigger sizes.
- If compute time is the main cost, DuckDB is cheaper. If memory is very limited, pandas is safer.

## AI summary

`src/ai_summary.py` reads the metrics, takes the middle value of the runs, and builds a short summary.

- The numbers in the summary are written by code, because a small local model misread numbers and comparisons in my first tests.
- The model fills in two short reasons: when to choose DuckDB and when to choose pandas. The sentence shape is fixed by the code.
- The model's reasons are checked before use. They are rejected if they contain digits or comparison words (faster, more, less and so on), or if DuckDB is not tied to compute time and pandas to memory.
- If the check fails, Ollama is not running, or the call fails, the script uses a rule-based sentence instead. The output file says which one was used.
- The model call is behind a small `SummaryProvider` class, so another model can be used later.
- Default provider: a local Ollama model (no API key, no cost). Settings through environment variables: `AI_MODEL` (default `llama3.2`) and `OLLAMA_URL` (default `http://localhost:11434`). I used `llama3.2:1b`.
- Limit: the small model often reuses the wording of the example in the prompt, so its contribution is small.

No secrets are used anywhere in this project.

## Tests

21 tests in `tests/`:

- duplicates are removed (both versions)
- bad rows are rejected (both versions)
- pandas and DuckDB give the same result
- running the pipeline twice gives the same result
- edge case: every row is invalid, so the output is empty
- failure cases: the AI provider crashes or is unreachable, so the fallback summary is used
- AI text is accepted only when it is correct, and rejected when it has numbers, comparison words, swapped advice, or the wrong format

## Assumptions and limits

- All data is synthetic. The cleaning rules are my own choices.
- Memory is checked every 10 ms, so a very short spike could be missed.
- Only time and memory are measured, not CPU use. DuckDB uses several cores, so faster does not always mean less total CPU work.
- The AI model may write a wrong number, so check the summary against the table.
- Results depend on the machine.

## Links

- Demo video: <add link>
- Design note: `docs/design_note.md`
