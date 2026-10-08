# Design Note: Cost-Aware Batch Pipeline

## Goal

Build one batch job two ways, measure what each costs in time and memory, and explain which one to choose and when.

## The job

The job reads order data, removes bad rows, and builds a daily table with the number of orders, the number of cancelled orders and revenue from completed orders. I chose this because it is a common reporting job and it uses the usual steps: read, clean, group and sum.

## Choices and why

**Synthetic data with planted mistakes.** The generator adds duplicate orders, missing customer ids and negative amounts. This gives the cleaning step real work, and the same seed always gives the same data, so results can be repeated.

**Two implementations.** Version A uses pandas in Python. Version B uses SQL in DuckDB, split into three files (raw, clean, daily). These are two common ways to do this job, and they work very differently inside: pandas loads and processes the data in Python, while DuckDB runs a database engine built for this kind of query.

**Same output, checked by code.** The two versions must give identical results. A test compares them, so the speed comparison is fair.

**Each run in its own process.** The benchmark starts a fresh process for every run, so memory from one run does not affect the next. Peak memory is read every 10 ms, and memory of child processes is included. I found this was needed on Windows, because the first version only measured a small launcher process and showed 4 MB.

**Three runs per size, middle value used.** One run can be thrown off by other programs on the computer. The middle of three is steadier.

**Metrics stored in a table.** Results go into a DuckDB table and a CSV file, so the AI summary and the README read the same numbers.

**AI behind a small interface.** The model call is in one class, so another model can be used later. The default is a local Ollama model, which costs nothing and needs no API key. If the call fails, a rule-based summary is used so the pipeline never breaks.

## What the results say

At 100k rows both versions take about 0.3 seconds. At 5.1M rows, pandas takes 13.17 seconds and DuckDB takes 1.36 seconds, which is 9.7 times faster. DuckDB uses about 38 percent more memory (1203 MB against 874 MB).

## Decision

Use DuckDB when this job runs on large data and compute time is the main cost. Use pandas when memory is limited or the data is small, because it is simpler and the speed difference does not matter there.

## Limits and what I would do next

- Only time and memory are measured. CPU use is not, and DuckDB uses several cores.
- Memory is sampled, so a very short spike could be missed.
- Results come from one laptop.
- Next steps: add a chunked pandas version, measure CPU time, and try a Parquet input file.
