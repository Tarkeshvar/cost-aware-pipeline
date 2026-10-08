import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate(n_rows, seed=42):
    rng = np.random.default_rng(seed)
    start = np.datetime64("2026-01-01T00:00:00")
    order_ts = start + rng.integers(0, 90 * 24 * 3600, n_rows).astype("timedelta64[s]")
    quantity = rng.integers(1, 6, n_rows)
    unit_price = np.round(rng.uniform(5, 500, n_rows), 2)

    df = pd.DataFrame(
        {
            "order_id": np.arange(1, n_rows + 1),
            "customer_id": pd.array(rng.integers(1, max(n_rows // 20, 100) + 1, n_rows), dtype="Int64"),
            "product_id": rng.integers(1, 501, n_rows),
            "quantity": quantity,
            "amount": np.round(quantity * unit_price, 2),
            "order_ts": pd.to_datetime(order_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "status": rng.choice(["completed", "cancelled", "returned"], size=n_rows, p=[0.85, 0.10, 0.05]),
        }
    )

    null_mask = rng.random(n_rows) < 0.01
    df.loc[null_mask, "customer_id"] = pd.NA

    bad_mask = rng.random(n_rows) < 0.01
    df.loc[bad_mask, "amount"] = -df.loc[bad_mask, "amount"]

    dupes = df.sample(frac=0.02, random_state=seed)
    df = pd.concat([df, dupes], ignore_index=True)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="data/orders.csv")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate(args.rows, args.seed)
    df.to_csv(out, index=False)
    print(f"wrote {len(df)} rows to {out}")


if __name__ == "__main__":
    main()