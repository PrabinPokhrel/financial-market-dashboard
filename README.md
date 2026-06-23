# Financial Market Dashboard

Real-time financial market analytics dashboard built on a modern data 
stack - Alpha Vantage API for live data, Supabase PostgreSQL for storage, 
Python pipeline for transformation, and Streamlit for visualisation.

## Dashboard Features

- Portfolio Overview: live price KPI cards with daily change, price trend 
  chart (100 days), and trading volume comparison across all 5 stocks
- Technical Analysis: 7-day and 30-day moving averages, candlestick chart 
  for last 30 days, selectable per stock
- Returns and Risk: daily returns time series, 30-day rolling volatility, 
  returns distribution histogram

## Stocks Tracked

AAPL, MSFT, GOOGL, AMZN, NVDA

## Tech Stack

- Data source: Alpha Vantage REST API (daily OHLCV)
- Database: Supabase PostgreSQL (cloud)
- Pipeline: Python, SQLAlchemy, psycopg2
- Transformations: SQL window functions (moving averages, daily returns, 
  rolling volatility) computed directly in PostgreSQL
- Visualisation: Streamlit, Plotly (line, candlestick, histogram, bar)
- Automation: GitHub Actions daily scheduler

## Data Pipeline
Alpha Vantage API

↓

Python ingestion script (src/ingest.py)

↓

Supabase PostgreSQL

raw_stock_prices        ← OHLCV data per ticker per day

mart_daily_returns      ← daily % return computed via SQL window function

mart_moving_averages    ← 7-day and 30-day MA via SQL window function

mart_volatility         ← 30-day rolling std dev via SQL window function

↓

Streamlit dashboard (app.py)

## Project Structure
financial-market-dashboard/

├── src/

│   └── ingest.py          # API ingestion and PostgreSQL pipeline

├── app.py                 # Streamlit dashboard

├── requirements.txt

└── .github/

└── workflows/

└── daily_run.yml  # GitHub Actions daily scheduler

## Key Results

- 500 rows loaded (100 days x 5 tickers) per pipeline run
- 4 PostgreSQL tables with computed analytics
- 3-tab interactive dashboard with live filtering by stock
- Candlestick chart, moving average overlays, volatility analysis

## How to Run Locally

1. Clone the repo
2. Install dependencies: pip install -r requirements.txt
3. Create .env file:
   ALPHA_VANTAGE_KEY=your_key
   SUPABASE_URL=your_supabase_connection_string
4. Run pipeline: python src/ingest.py
5. Run dashboard: streamlit run app.py

## Built by

Prabin Pokhrel
github.com/PrabinPokhrel
linkedin.com/in/prabin-pokhrel-23bab9279
