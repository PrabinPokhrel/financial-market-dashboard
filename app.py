import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine
from dotenv import load_dotenv
import sqlite3
import os
import re
import tempfile

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")

st.set_page_config(
    page_title="Financial Market Dashboard",
    page_icon="📈",
    layout="wide"
)

COLORS = {
    "AAPL" : "#378ADD",
    "MSFT" : "#1D9E75",
    "GOOGL": "#D85A30",
    "AMZN" : "#7F77DD",
    "NVDA" : "#E8A838",
}

# ── Data loading helpers ──────────────────────────────────────────────────────

@st.cache_resource
def get_engine():
    return create_engine(
        SUPABASE_URL,
        connect_args={"sslmode": "require"},
        pool_pre_ping=True
    )

@st.cache_data(ttl=3600)
def load_supabase(query):
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

def load_uploaded_csv(uploaded_file):
    df = pd.read_csv(uploaded_file, encoding='latin-1')
    df.columns = [
        c.strip().replace(" ", "_").replace("-", "_").lower()
        for c in df.columns
    ]
    return df

def detect_columns(df):
    cols = df.columns.tolist()
    date_col   = next((c for c in cols if any(k in c for k in ['date','time','day','month','year'])), cols[0])
    ticker_col = next((c for c in cols if any(k in c for k in ['ticker','symbol','stock','name','company'])), None)
    close_col  = next((c for c in cols if any(k in c for k in ['close','price','value','last'])), None)
    open_col   = next((c for c in cols if 'open' in c), None)
    high_col   = next((c for c in cols if 'high' in c), None)
    low_col    = next((c for c in cols if 'low' in c), None)
    volume_col = next((c for c in cols if 'volume' in c or 'vol' in c), None)
    return {
        'date': date_col, 'ticker': ticker_col,
        'close': close_col, 'open': open_col,
        'high': high_col, 'low': low_col, 'volume': volume_col
    }

# ── UI ────────────────────────────────────────────────────────────────────────

st.title("📈 Financial Market Dashboard")
st.markdown("Real-time stock analytics — price trends, moving averages, daily returns and volatility")
st.divider()

# Sidebar
with st.sidebar:
    st.header("Data Source")

    data_mode = st.radio(
        "Choose data source:",
        ["Live Portfolio (Supabase)", "Upload CSV"],
        index=1
    )

    st.divider()

    if data_mode == "Upload CSV":
        st.markdown("**Upload any financial CSV:**")
        st.caption("Supports OHLCV format or any price data with dates")
        uploaded_file = st.file_uploader("Drop CSV here", type=["csv"])
    else:
        uploaded_file = None

    st.divider()
    st.caption("Data: Alpha Vantage API")
    st.caption("Database: Supabase PostgreSQL")
    st.caption("Built by Prabin Pokhrel")
    st.caption("github.com/PrabinPokhrel")

# ── LIVE MODE ─────────────────────────────────────────────────────────────────

if data_mode == "Live Portfolio (Supabase)":

    try:
        raw_df  = load_supabase("SELECT * FROM raw_stock_prices ORDER BY ticker, date")
        ret_df  = load_supabase("SELECT * FROM mart_daily_returns ORDER BY ticker, date")
        ma_df   = load_supabase("SELECT * FROM mart_moving_averages ORDER BY ticker, date")
        vol_df  = load_supabase("SELECT * FROM mart_volatility ORDER BY ticker, date")

        TICKERS = sorted(raw_df["ticker"].unique().tolist())

        with st.sidebar:
            selected_tickers = st.multiselect(
                "Select stocks:", TICKERS, default=TICKERS
            )

        if not selected_tickers:
            st.warning("Please select at least one stock.")
            st.stop()

        filtered_raw = raw_df[raw_df["ticker"].isin(selected_tickers)]
        filtered_ret = ret_df[ret_df["ticker"].isin(selected_tickers)]
        filtered_ma  = ma_df[ma_df["ticker"].isin(selected_tickers)]
        filtered_vol = vol_df[vol_df["ticker"].isin(selected_tickers)]

        tab1, tab2, tab3 = st.tabs(["Portfolio Overview", "Technical Analysis", "Returns and Risk"])

        with tab1:
            st.subheader("Portfolio Overview")
            cols = st.columns(len(selected_tickers))
            for i, ticker in enumerate(selected_tickers):
                ticker_data = filtered_raw[filtered_raw["ticker"] == ticker].sort_values("date")
                if len(ticker_data) >= 2:
                    latest_close = ticker_data["close"].iloc[-1]
                    prev_close   = ticker_data["close"].iloc[-2]
                    change_pct   = (latest_close - prev_close) / prev_close * 100
                    cols[i].metric(
                        label=ticker,
                        value=f"${latest_close:.2f}",
                        delta=f"{change_pct:.2f}%"
                    )

            st.divider()
            st.subheader("Price Trend (Last 100 Days)")
            fig1 = go.Figure()
            for ticker in selected_tickers:
                data = filtered_raw[filtered_raw["ticker"] == ticker].sort_values("date")
                fig1.add_trace(go.Scatter(
                    x=data["date"], y=data["close"],
                    name=ticker,
                    line=dict(color=COLORS.get(ticker, "#333333"), width=2)
                ))
            fig1.update_layout(
                height=400, plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_title="Date", yaxis_title="Close Price (USD)",
                font=dict(family="Arial", size=12)
            )
            st.plotly_chart(fig1, use_container_width=True)

            st.subheader("Trading Volume")
            fig2 = go.Figure()
            for ticker in selected_tickers:
                data = filtered_raw[filtered_raw["ticker"] == ticker].sort_values("date")
                fig2.add_trace(go.Bar(
                    x=data["date"], y=data["volume"],
                    name=ticker,
                    marker_color=COLORS.get(ticker, "#333333"),
                    opacity=0.7
                ))
            fig2.update_layout(
                height=300, plot_bgcolor="white", paper_bgcolor="white",
                barmode="group",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_title="Date", yaxis_title="Volume",
                font=dict(family="Arial", size=12)
            )
            st.plotly_chart(fig2, use_container_width=True)

        with tab2:
            st.subheader("Technical Analysis — Moving Averages")
            selected_ticker_ma = st.selectbox("Select stock:", selected_tickers)
            ma_data = filtered_ma[filtered_ma["ticker"] == selected_ticker_ma].sort_values("date")

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=ma_data["date"], y=ma_data["close"],
                name="Close Price",
                line=dict(color=COLORS.get(selected_ticker_ma, "#333333"), width=1.5, dash="dot"),
                opacity=0.7
            ))
            fig3.add_trace(go.Scatter(
                x=ma_data["date"], y=ma_data["ma_7"],
                name="7-Day MA",
                line=dict(color="#D85A30", width=2)
            ))
            fig3.add_trace(go.Scatter(
                x=ma_data["date"], y=ma_data["ma_30"],
                name="30-Day MA",
                line=dict(color="#1D9E75", width=2)
            ))
            fig3.update_layout(
                height=450, plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_title="Date", yaxis_title="Price (USD)",
                title=f"{selected_ticker_ma} — Moving Averages",
                font=dict(family="Arial", size=12)
            )
            st.plotly_chart(fig3, use_container_width=True)

            st.subheader(f"{selected_ticker_ma} — Candlestick (Last 30 Days)")
            ohlc_data = filtered_raw[
                filtered_raw["ticker"] == selected_ticker_ma
            ].sort_values("date").tail(30)

            fig4 = go.Figure(data=[go.Candlestick(
                x=ohlc_data["date"],
                open=ohlc_data["open"], high=ohlc_data["high"],
                low=ohlc_data["low"],  close=ohlc_data["close"],
                increasing_line_color="#1D9E75",
                decreasing_line_color="#D85A30"
            )])
            fig4.update_layout(
                height=400, plot_bgcolor="white", paper_bgcolor="white",
                xaxis_rangeslider_visible=False,
                xaxis_title="Date", yaxis_title="Price (USD)",
                font=dict(family="Arial", size=12)
            )
            st.plotly_chart(fig4, use_container_width=True)

        with tab3:
            st.subheader("Daily Returns")
            fig5 = go.Figure()
            for ticker in selected_tickers:
                data = filtered_ret[filtered_ret["ticker"] == ticker].sort_values("date").dropna()
                fig5.add_trace(go.Scatter(
                    x=data["date"], y=data["daily_return"],
                    name=ticker,
                    line=dict(color=COLORS.get(ticker, "#333333"), width=1.5)
                ))
            fig5.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
            fig5.update_layout(
                height=400, plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_title="Date", yaxis_title="Daily Return (%)",
                font=dict(family="Arial", size=12)
            )
            st.plotly_chart(fig5, use_container_width=True)

            st.subheader("30-Day Rolling Volatility")
            fig6 = go.Figure()
            for ticker in selected_tickers:
                data = filtered_vol[filtered_vol["ticker"] == ticker].sort_values("date").dropna()
                fig6.add_trace(go.Scatter(
                    x=data["date"], y=data["volatility_30"],
                    name=ticker,
                    line=dict(color=COLORS.get(ticker, "#333333"), width=2),
                    fill="tozeroy", opacity=0.1
                ))
            fig6.update_layout(
                height=400, plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_title="Date", yaxis_title="Volatility",
                font=dict(family="Arial", size=12)
            )
            st.plotly_chart(fig6, use_container_width=True)

            st.subheader("Returns Distribution")
            fig7 = go.Figure()
            for ticker in selected_tickers:
                data = filtered_ret[
                    filtered_ret["ticker"] == ticker
                ].dropna(subset=["daily_return"])
                fig7.add_trace(go.Histogram(
                    x=data["daily_return"], name=ticker,
                    opacity=0.6,
                    marker_color=COLORS.get(ticker, "#333333"),
                    nbinsx=30
                ))
            fig7.update_layout(
                height=350, plot_bgcolor="white", paper_bgcolor="white",
                barmode="overlay",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_title="Daily Return (%)", yaxis_title="Frequency",
                font=dict(family="Arial", size=12)
            )
            st.plotly_chart(fig7, use_container_width=True)

    except Exception as e:
        st.warning("Live Portfolio mode requires a local database connection.")
        st.info("""
**To use Live Portfolio mode locally:**
1. Clone the repo
2. Add your Supabase credentials to `.env`
3. Run `python src/ingest.py` to load stock data
4. Run `streamlit run app.py`

**Try Upload CSV mode instead**  upload any stock CSV from Yahoo Finance or Stooq to explore the full dashboard.
        """)

# ── UPLOAD MODE ───────────────────────────────────────────────────────────────

else:
    if uploaded_file is None:
        st.info("Upload a CSV file in the sidebar to get started.")
        st.markdown("""
**Expected format — any of these work:**

| date | ticker | open | high | low | close | volume |
|------|--------|------|------|-----|-------|--------|
| 2024-01-01 | AAPL | 150 | 155 | 148 | 153 | 1000000 |

Or simply a date and price column — the app will detect columns automatically.
        """)
    else:
        df = load_uploaded_csv(uploaded_file)
        cols = detect_columns(df)

        st.success(f"Loaded: {uploaded_file.name} — {len(df):,} rows, {len(df.columns)} columns")

        date_col   = cols['date']
        close_col  = cols['close']
        ticker_col = cols['ticker']
        volume_col = cols['volume']
        open_col   = cols['open']
        high_col   = cols['high']
        low_col    = cols['low']

        if date_col and close_col:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df.dropna(subset=[date_col]).sort_values(date_col)

            if ticker_col and df[ticker_col].nunique() > 1:
                tickers = sorted(df[ticker_col].unique().tolist())
                with st.sidebar:
                    selected = st.multiselect("Select stocks:", tickers, default=tickers[:5])
                df = df[df[ticker_col].isin(selected)]
            else:
                selected = None

            tab1, tab2 = st.tabs(["Price Analysis", "Volume and Returns"])

            with tab1:
                st.subheader("Price Trend")
                fig1 = go.Figure()
                if ticker_col and selected:
                    for ticker in selected:
                        d = df[df[ticker_col] == ticker]
                        fig1.add_trace(go.Scatter(
                            x=d[date_col], y=d[close_col],
                            name=ticker, line=dict(width=2)
                        ))
                else:
                    fig1.add_trace(go.Scatter(
                        x=df[date_col], y=df[close_col],
                        name="Price", line=dict(color="#378ADD", width=2)
                    ))
                fig1.update_layout(
                    height=400, plot_bgcolor="white", paper_bgcolor="white",
                    xaxis_title="Date", yaxis_title="Price",
                    font=dict(family="Arial", size=12)
                )
                st.plotly_chart(fig1, use_container_width=True)

                if open_col and high_col and low_col:
                    st.subheader("Candlestick Chart (Last 60 rows)")
                    ohlc = df.tail(60)
                    if ticker_col and selected:
                        ohlc = df[df[ticker_col] == selected[0]].tail(60)
                    fig2 = go.Figure(data=[go.Candlestick(
                        x=ohlc[date_col],
                        open=ohlc[open_col], high=ohlc[high_col],
                        low=ohlc[low_col],   close=ohlc[close_col],
                        increasing_line_color="#1D9E75",
                        decreasing_line_color="#D85A30"
                    )])
                    fig2.update_layout(
                        height=400, plot_bgcolor="white", paper_bgcolor="white",
                        xaxis_rangeslider_visible=False,
                        font=dict(family="Arial", size=12)
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            with tab2:
                if volume_col:
                    st.subheader("Volume")
                    fig3 = go.Figure()
                    if ticker_col and selected:
                        for ticker in selected:
                            d = df[df[ticker_col] == ticker]
                            fig3.add_trace(go.Bar(
                                x=d[date_col], y=d[volume_col],
                                name=ticker, opacity=0.7
                            ))
                    else:
                        fig3.add_trace(go.Bar(
                            x=df[date_col], y=df[volume_col],
                            marker_color="#378ADD", opacity=0.7
                        ))
                    fig3.update_layout(
                        height=300, plot_bgcolor="white", paper_bgcolor="white",
                        xaxis_title="Date", yaxis_title="Volume",
                        font=dict(family="Arial", size=12)
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                st.subheader("Daily Returns")
                if ticker_col and selected:
                    for ticker in selected:
                        d = df[df[ticker_col] == ticker].copy()
                        d['return'] = d[close_col].pct_change() * 100
                        df.loc[df[ticker_col] == ticker, 'return'] = d['return']
                    fig4 = go.Figure()
                    for ticker in selected:
                        d = df[df[ticker_col] == ticker].dropna(subset=['return'])
                        fig4.add_trace(go.Scatter(
                            x=d[date_col], y=d['return'],
                            name=ticker, line=dict(width=1.5)
                        ))
                else:
                    df['return'] = df[close_col].pct_change() * 100
                    fig4 = go.Figure()
                    fig4.add_trace(go.Scatter(
                        x=df[date_col], y=df['return'],
                        line=dict(color="#378ADD", width=1.5)
                    ))
                fig4.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
                fig4.update_layout(
                    height=350, plot_bgcolor="white", paper_bgcolor="white",
                    xaxis_title="Date", yaxis_title="Daily Return (%)",
                    font=dict(family="Arial", size=12)
                )
                st.plotly_chart(fig4, use_container_width=True)

        else:
            st.error("Could not detect date or price columns. Please check your CSV format.")
            st.dataframe(df.head())