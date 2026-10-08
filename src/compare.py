import sys

import pandas as pd

from pipeline_duckdb import run_duckdb
from pipeline_pandas import run_pandas

path = sys.argv[1] if len(sys.argv) > 1 else "data/orders.csv"
a, sa = run_pandas(path)
b, sb = run_duckdb(path)
print(sa, sb)
pd.testing.assert_frame_equal(a, b, check_dtype=False)
print("outputs match")