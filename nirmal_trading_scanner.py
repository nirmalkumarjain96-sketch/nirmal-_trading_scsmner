import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import time

st.set_page_config(page_title="NIRMAL AI Trading Scanner", layout="wide")
st.title("📈 NIRMAL AI Trading Scanner")
st.caption("Nifty 50 • 15-minute trend scan • BUY / SELL / WAIT")

# Free Yahoo Finance symbols. Constituents can change; update this list when Nifty 50 changes.
NIFTY50 = [
    "ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK",
    "BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL",
    "CIPLA","COALINDIA","DRREDDY","EICHERMOT","ETERNAL",
    "GRASIM","HCLTECH","HDFCBANK","HDFCLIFE","HINDALCO",
    "HINDUNILVR","ICICIBANK","INDUSINDBK","INFY","ITC",
    "JIOFIN","JSWSTEEL","KOTAKBANK","LT","M&M",
    "MARUTI","NESTLEIND","NTPC","ONGC","POWERGRID",
    "RELIANCE","SBILIFE","SBIN","SHRIRAMFIN","SUNPHARMA",
    "TATACONSUM","TATAMOTORS","TATASTEEL","TCS","TECHM",
    "TITAN","TRENT","ULTRACEMCO","WIPRO","MAXHEALTH"
]
SYMBOLS = [s + ".NS" for s in NIFTY50]

st.warning(
    "महत्वपूर्ण: यह शुरुआती FREE-data scanner है। Yahoo Finance का डेटा delayed/कभी-कभी अधूरा हो सकता है; "
    "यह exchange-grade live feed नहीं है। सिग्नल को Kotak Neo में चार्ट देखकर verify करें। "
    "यह कोई ऑर्डर नहीं लगाता और मुनाफे की गारंटी नहीं देता।"
)

col1, col2, col3 = st.columns(3)
with col1:
    interval = st.selectbox("Candle timeframe", ["15m", "30m"], index=0)
with col2:
    period = st.selectbox("History", ["5d", "1mo"], index=0)
with col3:
    refresh = st.checkbox("हर 15 मिनट में refresh", value=True)

def analyze(symbol):
    try:
        df = yf.download(
            symbol, period=period, interval=interval,
            auto_adjust=False, progress=False, threads=False
        )
        if df is None or df.empty or len(df) < 30:
            return None

        # yfinance may return MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close", "High", "Low", "Volume"]).copy()
        if len(df) < 25:
            return None

        close = df["Close"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        vol = df["Volume"].astype(float)

        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()

        # RSI(14)
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))

        # Intraday VWAP from available bars
        typical = (high + low + close) / 3
        dates = df.index.date
        cum_pv = (typical * vol).groupby(dates).cumsum()
        cum_vol = vol.groupby(dates).cumsum().replace(0, float("nan"))
        vwap = cum_pv / cum_vol

        last = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        e9, e21 = float(ema9.iloc[-1]), float(ema21.iloc[-1])
        rv = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
        vw = float(vwap.iloc[-1]) if pd.notna(vwap.iloc[-1]) else last
        avgvol = float(vol.iloc[-21:-1].mean()) if len(vol) > 21 else float(vol.iloc[:-1].mean())
        vol_ratio = float(vol.iloc[-1] / avgvol) if avgvol > 0 else 0
        momentum = (last / prev - 1) * 100 if prev else 0

        bullish = last > e9 > e21 and last > vw and rv >= 55 and vol_ratio >= 1.2 and momentum > 0
        bearish = last < e9 < e21 and last < vw and rv <= 45 and vol_ratio >= 1.2 and momentum < 0

        if bullish:
            signal = "🟢 STRONG BUY"
            sl = min(float(low.iloc[-1]), e21)
            risk = max(last - sl, last * 0.003)
            t1, t2 = last + risk, last + 2*risk
        elif bearish:
            signal = "🔴 STRONG SELL"
            sl = max(float(high.iloc[-1]), e21)
            risk = max(sl - last, last * 0.003)
            t1, t2 = last - risk, last - 2*risk
        else:
            signal = "🟡 WAIT"
            sl = t1 = t2 = float("nan")

        return {
            "Share": symbol.replace(".NS", ""),
            "Signal": signal,
            "LTP*": round(last, 2),
            "RSI": round(rv, 1),
            "Volume vs Avg": round(vol_ratio, 2),
            "EMA 9": round(e9, 2),
            "EMA 21": round(e21, 2),
            "VWAP": round(vw, 2),
            "15m Change %": round(momentum, 2),
            "Indicative SL": round(sl, 2) if pd.notna(sl) else "-",
            "Target 1": round(t1, 2) if pd.notna(t1) else "-",
            "Target 2": round(t2, 2) if pd.notna(t2) else "-",
        }
    except Exception:
        return None

if st.button("🔍 अभी Nifty 50 स्कैन करें", type="primary"):
    progress = st.progress(0)
    status = st.empty()
    rows = []
    for i, sym in enumerate(SYMBOLS):
        status.write(f"स्कैन हो रहा है: {sym.replace('.NS','')} ({i+1}/{len(SYMBOLS)})")
        result = analyze(sym)
        if result:
            rows.append(result)
        progress.progress((i+1)/len(SYMBOLS))
        time.sleep(0.12)
    status.empty()
    progress.empty()

    if rows:
        result_df = pd.DataFrame(rows)
        result_df["_rank"] = result_df["Signal"].map({"🟢 STRONG BUY": 0, "🔴 STRONG SELL": 1, "🟡 WAIT": 2})
        result_df = result_df.sort_values(["_rank", "Volume vs Avg"], ascending=[True, False]).drop(columns="_rank")
        buys = result_df[result_df["Signal"].str.contains("BUY")]
        sells = result_df[result_df["Signal"].str.contains("SELL")]
        a, b, c = st.columns(3)
        a.metric("BUY signals", len(buys))
        b.metric("SELL signals", len(sells))
        c.metric("WAIT", len(result_df) - len(buys) - len(sells))
        st.subheader("सभी स्कैन परिणाम")
        st.dataframe(result_df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ CSV डाउनलोड करें", result_df.to_csv(index=False), "nirmal_scanner_results.csv", "text/csv")
        st.caption("*LTP = Yahoo Finance से मिला अंतिम उपलब्ध candle close; जरूरी नहीं कि यह real-time price हो।")
    else:
        st.error("डेटा नहीं मिला। इंटरनेट कनेक्शन या Yahoo Finance data availability जाँचें और फिर कोशिश करें।")
else:
    st.info("स्कैन शुरू करने के लिए ऊपर बटन दबाएँ। पहली बार 50 शेयर स्कैन होने में कुछ समय लग सकता है।")

st.divider()
st.subheader("सिग्नल कैसे बनता है?")
st.write(
    "STRONG BUY: Price > EMA 9 > EMA 21, Price > VWAP, RSI ≥ 55, "
    "Volume पिछले 20 candles के औसत से कम-से-कम 1.2 गुना और पिछली candle से price ऊपर।"
)
st.write(
    "STRONG SELL: इसके उलट शर्तें — Price < EMA 9 < EMA 21, Price < VWAP, "
    "RSI ≤ 45, Volume ≥ 1.2 गुना और पिछली candle से price नीचे।"
)
st.caption("यह नियम-आधारित शैक्षिक स्कैनर है, AI भविष्यवाणी नहीं। Options (Nifty/Bank Nifty CE/PE) के लिए अलग live option-chain data feed की जरूरत होगी।")
