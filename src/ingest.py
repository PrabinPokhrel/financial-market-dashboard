"""
Financial Market Data Ingestion
Fetches daily OHLCV stock data from Alpha Vantage and loads into Supabase PostgreSQL
"""

import os
import requests
import pandas as pd
import time
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
SUPABASE_URL      = os.getenv("SUPABASE_URL")

TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

def fetch_stock_data(ticker):
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=TIME_SERIES_DAILY"
        f"&symbol={ticker}"
        f"&outputsize=compact"
        f"&apikey={ALPHA_VANTAGE_KEY}"
    )
    print(f"Fetching {ticker}...")
    response = requests.get(url, timeout=30)
    data     = response.json()

    if "Time Series (Daily)" not in data:
        print(f"Error fetching {ticker}: {data.get('Note', data.get('Information', 'Unknown error'))}")
        return None

    ts = data["Time Series (Daily)"]
    rows = []
    for date_str, values in ts.items():
        rows.append({
            "ticker"    : ticker,
            "date"      : date_str,
            "open"      : float(values["1. open"]),
            "high"      : float(values["2. high"]),
            "low"       : float(values["3. low"]),
            "close"     : float(values["4. close"]),
            "volume"    : int(values["5. volume"]),
        })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    print(f"  {ticker}: {len(df)} rows fetched")
    return df

def create_tables(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_stock_prices (
                id          SERIAL PRIMARY KEY,
                ticker      VARCHAR(10)  NOT NULL,
                date        DATE         NOT NULL,
                open        NUMERIC(12,4),
                high        NUMERIC(12,4),
                low         NUMERIC(12,4),
                close       NUMERIC(12,4),
                volume      BIGINT,
                loaded_at   TIMESTAMP DEFAULT NOW(),
                UNIQUE(ticker, date)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mart_daily_returns (
                ticker          VARCHAR(10),
                date            DATE,
                close           NUMERIC(12,4),
                daily_return    NUMERIC(10,6),
                PRIMARY KEY (ticker, date)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mart_moving_averages (
                ticker      VARCHAR(10),
                date        DATE,
                close       NUMERIC(12,4),
                ma_7        NUMERIC(12,4),
                ma_30       NUMERIC(12,4),
                PRIMARY KEY (ticker, date)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mart_volatility (
                ticker          VARCHAR(10),
                date            DATE,
                volatility_30   NUMERIC(10,6),
                PRIMARY KEY (ticker, date)
            )
        """))
        conn.commit()
    print("Tables created successfully")

def load_raw_data(engine, df, ticker):
    with engine.connect() as conn:
        for _, row in df.iterrows():
            conn.execute(text("""
                INSERT INTO raw_stock_prices (ticker, date, open, high, low, close, volume)
                VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
                ON CONFLICT (ticker, date) DO UPDATE SET
                    open      = EXCLUDED.open,
                    high      = EXCLUDED.high,
                    low       = EXCLUDED.low,
                    close     = EXCLUDED.close,
                    volume    = EXCLUDED.volume,
                    loaded_at = NOW()
            """), {
                "ticker" : row["ticker"],
                "date"   : row["date"].date(),
                "open"   : row["open"],
                "high"   : row["high"],
                "low"    : row["low"],
                "close"  : row["close"],
                "volume" : row["volume"],
            })
        conn.commit()
    print(f"  {ticker}: loaded to raw_stock_prices")

def build_mart_daily_returns(engine, ticker):
    with engine.connect() as conn:
        conn.execute(text("""
            DELETE FROM mart_daily_returns WHERE ticker = :ticker
        """), {"ticker": ticker})

        conn.execute(text("""
            INSERT INTO mart_daily_returns (ticker, date, close, daily_return)
            SELECT
                ticker,
                date,
                close,
                ROUND(
                    (close - LAG(close) OVER (PARTITION BY ticker ORDER BY date))
                    / NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY date), 0)
                    * 100, 6
                ) AS daily_return
            FROM raw_stock_prices
            WHERE ticker = :ticker
            ORDER BY date
        """), {"ticker": ticker})
        conn.commit()
    print(f"  {ticker}: daily returns computed")

def build_mart_moving_averages(engine, ticker):
    with engine.connect() as conn:
        conn.execute(text("""
            DELETE FROM mart_moving_averages WHERE ticker = :ticker
        """), {"ticker": ticker})

        conn.execute(text("""
            INSERT INTO mart_moving_averages (ticker, date, close, ma_7, ma_30)
            SELECT
                ticker,
                date,
                close,
                ROUND(AVG(close) OVER (
                    PARTITION BY ticker ORDER BY date
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ), 4) AS ma_7,
                ROUND(AVG(close) OVER (
                    PARTITION BY ticker ORDER BY date
                    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                ), 4) AS ma_30
            FROM raw_stock_prices
            WHERE ticker = :ticker
            ORDER BY date
        """), {"ticker": ticker})
        conn.commit()
    print(f"  {ticker}: moving averages computed")

def build_mart_volatility(engine, ticker):
    with engine.connect() as conn:
        conn.execute(text("""
            DELETE FROM mart_volatility WHERE ticker = :ticker
        """), {"ticker": ticker})

        conn.execute(text("""
            INSERT INTO mart_volatility (ticker, date, volatility_30)
            SELECT
                r.ticker,
                r.date,
                ROUND(STDDEV(r.daily_return) OVER (
                    PARTITION BY r.ticker ORDER BY r.date
                    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                ), 6) AS volatility_30
            FROM mart_daily_returns r
            WHERE r.ticker = :ticker
            ORDER BY r.date
        """), {"ticker": ticker})
        conn.commit()
    print(f"  {ticker}: volatility computed")

def run_pipeline():
    print("=" * 55)
    print("FINANCIAL DATA PIPELINE START")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    engine = create_engine(SUPABASE_URL)
    create_tables(engine)

    for ticker in TICKERS:
        df = fetch_stock_data(ticker)
        time.sleep(15)  # wait 15 seconds between requests
        if df is not None:
            load_raw_data(engine, df, ticker)
            build_mart_daily_returns(engine, ticker)
            build_mart_moving_averages(engine, ticker)
            build_mart_volatility(engine, ticker)
            print(f"{ticker}: pipeline complete")
        print()

    print("=" * 55)
    print("PIPELINE COMPLETE")
    print("=" * 55)

if __name__ == "__main__":
    run_pipeline()