import sys

import pandas as pd


def run_pandas(csv_path):
    df = pd.read_csv(csv_path, parse_dates=["order_ts"])
    rows_in = len(df)

    df = df.dropna(subset=["customer_id"])
    df = df[df["amount"] > 0]
    df = df.drop_duplicates(subset="order_id", keep="first")
    rows_out = len(df)

    df = df.assign(
        order_date=df["order_ts"].dt.strftime("%Y-%m-%d"),
        completed_amount=df["amount"].where(df["status"] == "completed", 0.0),
        is_cancelled=(df["status"] == "cancelled").astype(int),
    )

    daily = (
        df.groupby("order_date", as_index=False)
        .agg(
            orders=("order_id", "count"),
            cancelled=("is_cancelled", "sum"),
            revenue=("completed_amount", "sum"),
        )
        .sort_values("order_date")
        .reset_index(drop=True)
    )
    daily["revenue"] = daily["revenue"].round(2)
    return daily, {"rows_in": rows_in, "rows_out": rows_out}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/orders.csv"
    result, stats = run_pandas(path)
    print(stats)
    print(result.head())
    print(f"days: {len(result)}")