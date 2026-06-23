import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")

st.set_page_config(
    page_title="Financial Market Dashboard",
    page_icon="📈",
    layout="wide"
)

@st.cache_resource
def get_engine():
    return create_engine(SUPABASE_URL)

@st.cache_data(ttl=3600)
def load_data(query):
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

# ── Load all data ─────────────────────────────────────────────────────────────
raw_df  = load_data("SELECT * FROM raw_stock_prices ORDER BY ticker, date")
ret_df  = load_data("SELECT * FROM mart_daily_returns ORDER BY ticker, date")
ma_df   = load_data("SELECT * FROM mart_moving_averages ORDER BY ticker, date")
vol_df  = load_data("SELECT * FROM mart_volatility ORDER BY ticker, date")

TICKERS = sorted(raw_df["ticker"].unique().tolist())
COLORS  = {
    "AAPL" : "#378ADD",
    "MSFT" : "#1D9E75",
    "GOOGL": "#D85A30",
    "AMZN" : "#7F77DD",
    "NVDA" : "#E8A838",
}

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📈 Financial Market Dashboard")
st.markdown("Real-time stock analytics — price trends, moving averages, daily returns and volatility")
st.divider()

# Sidebar
with st.sidebar:
    st.header("Controls")
    selected_tickers = st.multiselect(
        "Select stocks:",
        TICKERS,
        default=TICKERS
    )
    st.divider()
    st.caption("Data: Alpha Vantage API")
    st.caption("Database: Supabase PostgreSQL")
    st.caption("Built by Prabin Pokhrel")

if not selected_tickers:
    st.warning("Please select at least one stock.")
    st.stop()

filtered_raw = raw_df[raw_df["ticker"].isin(selected_tickers)]
filtered_ret = ret_df[ret_df["ticker"].isin(selected_tickers)]
filtered_ma  = ma_df[ma_df["ticker"].isin(selected_tickers)]
filtered_vol = vol_df[vol_df["ticker"].isin(selected_tickers)]

# ── PAGE 1: Portfolio Overview ─────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Portfolio Overview", "Technical Analysis", "Returns and Risk"])

with tab1:
    st.subheader("Portfolio Overview")

    # KPI cards
    cols = st.columns(len(selected_tickers))
    for i, ticker in enumerate(selected_tickers):
        ticker_data = filtered_raw[filtered_raw["ticker"] == ticker].sort_values("date")
        if len(ticker_data) >= 2:
            latest_close = ticker_data["close"].iloc[-1]
            prev_close   = ticker_data["close"].iloc[-2]
            change_pct   = (latest_close - prev_close) / prev_close * 100
            color        = "normal" if change_pct >= 0 else "inverse"
            cols[i].metric(
                label=ticker,
                value=f"${latest_close:.2f}",
                delta=f"{change_pct:.2f}%"
            )

    st.divider()

    # Price trend chart
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
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="Date",
        yaxis_title="Close Price (USD)",
        font=dict(family="Arial", size=12)
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Volume chart
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
        height=300,
        plot_bgcolor="white",
        paper_bgcolor="white",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="Date",
        yaxis_title="Volume",
        font=dict(family="Arial", size=12)
    )
    st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("Technical Analysis — Moving Averages")

    selected_ticker_ma = st.selectbox("Select stock for technical analysis:", selected_tickers)

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
        height=450,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        title=f"{selected_ticker_ma} — Price with 7-Day and 30-Day Moving Averages",
        font=dict(family="Arial", size=12)
    )
    st.plotly_chart(fig3, use_container_width=True)

    # OHLC candlestick
    st.subheader(f"{selected_ticker_ma} — Candlestick Chart (Last 30 Days)")
    ohlc_data = filtered_raw[
        filtered_raw["ticker"] == selected_ticker_ma
    ].sort_values("date").tail(30)

    fig4 = go.Figure(data=[go.Candlestick(
        x=ohlc_data["date"],
        open=ohlc_data["open"],
        high=ohlc_data["high"],
        low=ohlc_data["low"],
        close=ohlc_data["close"],
        increasing_line_color="#1D9E75",
        decreasing_line_color="#D85A30"
    )])
    fig4.update_layout(
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_rangeslider_visible=False,
        xaxis_title="Date",
        yaxis_title="Price (USD)",
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
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="Date",
        yaxis_title="Daily Return (%)",
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
            fill="tozeroy",
            fillcolor=COLORS.get(ticker, "#333333"),
            opacity=0.1
        ))
    fig6.update_layout(
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="Date",
        yaxis_title="Volatility (Std Dev of Daily Returns)",
        font=dict(family="Arial", size=12)
    )
    st.plotly_chart(fig6, use_container_width=True)

    # Returns distribution
    st.subheader("Returns Distribution")
    fig7 = go.Figure()
    for ticker in selected_tickers:
        data = filtered_ret[
            filtered_ret["ticker"] == ticker
        ].dropna(subset=["daily_return"])
        fig7.add_trace(go.Histogram(
            x=data["daily_return"],
            name=ticker,
            opacity=0.6,
            marker_color=COLORS.get(ticker, "#333333"),
            nbinsx=30
        ))
    fig7.update_layout(
        height=350,
        plot_bgcolor="white",
        paper_bgcolor="white",
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="Daily Return (%)",
        yaxis_title="Frequency",
        font=dict(family="Arial", size=12)
    )
    st.plotly_chart(fig7, use_container_width=True)