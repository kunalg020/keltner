
from flask import Flask
import pandas as pd
import numpy as np
import requests
import json

app = Flask(__name__)

def load_config():
    with open("dhan_screener_config.json") as f:
        return json.load(f)

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

@app.route("/", methods=["GET"])
def run_screener():
    config = load_config()
    headers = {
        "access-token": config["dhan"]["access_token"],
        "client-id": config["dhan"]["client_id"]
    }
    base_url = "https://api.dhan.co/market/quotes/intraday/candle"
    alerts = []

    for symbol in config["symbols"]:
        try:
            params_daily = {
                "security_id": symbol,
                "exchange": "NSE",
                "instrument": "NSE_EQ",
                "interval": "1d",
                "limit": 30
            }
            res = requests.get(base_url, headers=headers, params=params_daily, timeout=10)
            df = pd.DataFrame(res.json().get("data", []))
            if df.empty: continue
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            df["ema88"] = df["close"].ewm(span=88).mean()
            df["tr"] = df[["high", "low", "close"]].apply(
                lambda row: max(row["high"] - row["low"], abs(row["high"] - row["close"]), abs(row["low"] - row["close"])), axis=1)
            df["atr"] = df["tr"].rolling(21).mean()
            df["kc_upper"] = df["close"].rolling(21).mean() + df["atr"]
            df["kc_middle"] = df["close"].rolling(21).mean()
            df["rsi"] = df["close"].diff().apply(lambda x: x if x > 0 else 0).rolling(14).mean() /                         df["close"].diff().abs().rolling(14).mean() * 100
            latest = df.iloc[-1]
            if latest["close"] > latest["kc_upper"] and latest["close"] > latest["ema88"] and latest["rsi"] > 60:
                alerts.append(f"{symbol} matched on Daily TF.")
        except Exception as e:
            print(f"Error with {symbol}: {e}")

    if alerts:
        msg = "🔔 Nifty 50 Screener Alerts:
" + "
".join(alerts)
        send_telegram_message(config["telegram"]["bot_token"], config["telegram"]["chat_id"], msg)
        return msg
    return "No signals."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
