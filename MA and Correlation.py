# ============================================================
# Daily Moving Average Strategy with Email Alerts & Correlation
# Headless Version with Logging
# ============================================================

import pandas as pd
import numpy as np
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import time
from datetime import datetime
import os

# =====================
# CONFIGURATION
# =====================
symbol = "XRPUSDT"
compare_symbol = "BTCUSDT"
interval = "1d"
limit = 300

EMAIL_SENDER = "dagiwonpotra@gmail.com"
EMAIL_PASSWORD = "qjmebnsrngzdyogx"
EMAIL_RECEIVER = "dagiwonpotra2@gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Log file path
LOG_FILE = "trading_bot_log.csv"

# =====================
# FUNCTIONS
# =====================
def send_email(subject, message):
    """Send email notification"""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"📧 Email sent: {subject}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def get_data_public(symbol="XRPUSDT", interval="1d", limit=300):
    """Fetch historical klines from Binance public API"""
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    klines = resp.json()
    df = pd.DataFrame(klines, columns=[
        "Open Time", "Open", "High", "Low", "Close", "Volume",
        "Close Time", "Quote Asset Volume", "Number of Trades",
        "Taker Buy Base", "Taker Buy Quote", "Ignore"
    ])
    df["Date"] = pd.to_datetime(df["Open Time"], unit="ms")
    df["Close"] = df["Close"].astype(float)
    df.set_index("Date", inplace=True)
    return df[["Close"]]

def calculate_moving_averages(df):
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    return df

def find_crossovers(df):
    df["Crossover"] = np.where(df["MA20"] > df["MA50"], 1, 0)
    df["Signal"] = df["Crossover"].diff()
    return df

def calculate_correlation(symbol1="XRPUSDT", symbol2="BTCUSDT", window=30):
    df1 = get_data_public(symbol1)
    df2 = get_data_public(symbol2)
    combined = pd.concat([df1["Close"], df2["Close"]], axis=1)
    combined.columns = [symbol1, symbol2]
    combined.dropna(inplace=True)
    combined["ret1"] = combined[symbol1].pct_change()
    combined["ret2"] = combined[symbol2].pct_change()
    combined["corr"] = combined["ret1"].rolling(window).corr(combined["ret2"])
    return combined

def log_signal(date, symbol, price, correlation, signal_type):
    """Append daily signal to log CSV"""
    log_exists = os.path.isfile(LOG_FILE)
    df_log = pd.DataFrame([{
        "Date": date,
        "Symbol": symbol,
        "Price": price,
        "Correlation": correlation,
        "Signal": signal_type
    }])
    if log_exists:
        df_log.to_csv(LOG_FILE, mode="a", header=False, index=False)
    else:
        df_log.to_csv(LOG_FILE, mode="w", header=True, index=False)
    print(f"📝 Logged {signal_type} signal for {symbol} on {date}")

# =====================
# TRADING BOT FUNCTION
# =====================
def run_trading_bot():
    print(f"\n⏰ Running trading bot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    df = get_data_public(symbol, interval, limit)
    df = calculate_moving_averages(df)
    df = find_crossovers(df)

    combined = calculate_correlation(symbol, compare_symbol)
    latest_corr = combined["corr"].iloc[-1] if not combined.empty else np.nan
    print(f"📈 Latest correlation ({symbol} vs {compare_symbol}): {latest_corr:.2f}")

    last = df.iloc[-1]
    date_str = last.name.strftime('%Y-%m-%d')
    signal_type = "No Signal"

    if last["MA20"] > last["MA50"] and last["Close"] > last["MA200"] and latest_corr > 0.5:
        signal_type = "BUY"
        alert = f"🚀 BUY Signal for {symbol}\nPrice: {last['Close']}\nCorr: {latest_corr:.2f}\nTrend: Bullish"
        print(alert)
        send_email(f"{symbol} BUY Alert", alert)
    elif last["MA20"] < last["MA50"] and last["Close"] < last["MA200"]:
        signal_type = "SELL"
        alert = f"⚠️ SELL Signal for {symbol}\nPrice: {last['Close']}\nCorr: {latest_corr:.2f}\nTrend: Bearish"
        print(alert)
        send_email(f"{symbol} SELL Alert", alert)
    else:
        print("ℹ️ No clear signal right now.")

    # Log the signal
    log_signal(date_str, symbol, last["Close"], latest_corr, signal_type)

# =====================
# SCHEDULER
# =====================
schedule.every().day.at("09:00").do(run_trading_bot)
print("📅 Headless scheduler with logging started. Bot will run every day at 09:00 AM.")

# Keep script running
while True:
    schedule.run_pending()
    time.sleep(60)
