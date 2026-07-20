"""
HalalBot - Bot de paper trading avec vraies donnees de marche
100% halal - Sans interets, sans levier, sans CFD
Cycle toutes les 4h - Forex Factory RSS - RSI corrige
"""
import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

DATA_FILE = "data/state.json"

INSTRUMENTS = {
    "XAUUSD": {"name": "Or / Gold", "type": "commodity"},
    "BTC": {"name": "Bitcoin", "type": "crypto"},
    "NVDA": {"name": "Nvidia", "type": "stock"},
    "MSFT": {"name": "Microsoft", "type": "stock"},
    "AAPL": {"name": "Apple", "type": "stock"},
    "TSLA": {"name": "Tesla", "type": "stock"},
    "AMZN": {"name": "Amazon", "type": "stock"},
    "GOOGL": {"name": "Alphabet", "type": "stock"},
    "LLY": {"name": "Eli Lilly", "type": "stock"},
    "ASML": {"name": "ASML", "type": "stock"},
}

INITIAL_CAPITAL = 1000.0
RISK_PER_TRADE = 0.20
MAX_POSITION = 200.0


def load_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "capital": INITIAL_CAPITAL,
        "positions": [],
        "trades": [],
        "price_history": {k: [] for k in INSTRUMENTS},
        "last_update": None,
    }


def save_state(state):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_btc_price():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        return float(r.json()["bitcoin"]["usd"])
    except Exception as e:
        print(f"Erreur BTC: {e}")
        return None


def get_gold_price():
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": "XAU",
                "to_currency": "USD",
                "apikey": ALPHA_VANTAGE_KEY,
            },
            timeout=10,
        )
        data = r.json()
        rate = data.get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
        return float(rate) if rate else None
    except Exception as e:
        print(f"Erreur Gold: {e}")
        return None


def get_stock_price(symbol):
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": ALPHA_VANTAGE_KEY,
            },
            timeout=10,
        )
        data = r.json()
        price = data.get("Global Quote", {}).get("05. price")
        return float(price) if price else None
    except Exception as e:
        print(f"Erreur {symbol}: {e}")
        return None


def get_high_impact_news():
    HIGH_IMPACT_KEYWORDS = [
        "interest rate", "nonfarm", "non-farm", "CPI", "GDP", "unemployment",
        "federal reserve", "fed", "ECB", "BOE", "inflation", "FOMC",
        "rate decision", "central bank", "war", "iran", "strike", "conflict",
        "taux directeur", "chomage", "banque centrale", "guerre"
    ]
    sources = [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
        "https://www.investing.com/rss/news_25.rss",
    ]
    for url in sources:
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                print(f"Source non disponible: {r.status_code}")
                continue
            root = ET.fromstring(r.content)
            items = root.findall(".//item") or root.findall(".//event")
            for item in items:
                title = (item.findtext("title") or "").lower()
                for kw in HIGH_IMPACT_KEYWORDS:
                    if kw.lower() in title:
                        print(f"News detectee: {item.findtext('title')}")
                        return True, item.findtext("title", "News importante")
        except Exception as e:
            print(f"Erreur source {url}: {e}")
            continue
    return False, None



def fetch_all_prices():
    prices = {}
    prices["BTC"] = get_btc_price()
    time.sleep(2)
    prices["XAUUSD"] = get_gold_price()
    time.sleep(15)
    stock_symbols = ["NVDA", "MSFT", "AAPL", "TSLA", "AMZN", "GOOGL", "LLY", "ASML"]
    for sym in stock_symbols:
        prices[sym] = get_stock_price(sym)
        time.sleep(15)
    return prices


def calculate_rsi(history, period=14):
    """Calcul RSI corrige - retourne None si historique insuffisant"""
    if len(history) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(history)):
        diff = history[i] - history[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    if not gains and not losses:
        return None
        avg_gain = sum(gains[-period:]) / period if gains else 0.0001
    avg_loss = sum(losses[-period:]) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)


def analyze_signal(symbol, current_price, history):
    if len(history) < 10:
        return "ATTENDRE", "Historique insuffisant"

    recent = history[-10:]
    avg = sum(recent) / len(recent)
    rsi = calculate_rsi(history)

    if rsi is None:
        rsi_label = "RSI=N/A"
        rsi_ok_buy = True
        rsi_ok_sell = True
    else:
        rsi_label = f"RSI={rsi}"
        rsi_ok_buy = rsi < 70
        rsi_ok_sell = rsi > 30

    above_ma = current_price > avg * 1.005
    below_ma = current_price < avg * 0.995

    if above_ma and rsi_ok_buy:
        return "ACHETER", f"Prix au-dessus MM10, {rsi_label}"
    elif below_ma and rsi_ok_sell:
        return "VENDRE", f"Prix sous MM10, {rsi_label}"
    else:
        return "ATTENDRE", f"Pas de signal clair, {rsi_label}"


def run_bot():
    state = load_state()
    now = datetime.now(timezone.utc)
    print(f"=== HalalBot - {now.isoformat()} ===")

        has_news, news_event = get_high_impact_news()
    if has_news:
        print(f"News a fort impact detectee: {news_event}")
    else:
        print("Pas de news a fort impact detectee")

    prices = fetch_all_prices()
    print(f"Prix recuperes: {prices}")

    signals = {}
    for symbol, price in prices.items():
        if price is None:
            continue

        history = state["price_history"].setdefault(symbol, [])
        history.append(price)
        state["price_history"][symbol] = history[-50:]

        signal, reason = analyze_signal(symbol, price, history)
        signals[symbol] = {"signal": signal, "reason": reason, "price": price}
        print(f"{symbol}: {price} -> {signal} ({reason})")

        if signal == "ACHETER" and not has_news:
            already_open = any(p["symbol"] == symbol for p in state["positions"])
            if not already_open and state["capital"] > 100:
                amount = min(state["capital"] * RISK_PER_TRADE, MAX_POSITION)
                qty = amount / price
                position = {
                    "symbol": symbol,
                    "name": INSTRUMENTS[symbol]["name"],
                    "entry_price": price,
                    "qty": qty,
                    "amount": amount,
                    "tp": round(price * 1.025, 2),
                    "sl": round(price * 0.988, 2),
                    "open_time": now.isoformat(),
                }
                state["positions"].append(position)
                state["capital"] = round(state["capital"] - amount, 2)
                print(f"  -> POSITION OUVERTE: {amount:.2f} EUR sur {symbol}")

        remaining = []
        for pos in state["positions"]:
            if pos["symbol"] != symbol:
                remaining.append(pos)
                continue
            if price >= pos["tp"] or price <= pos["sl"]:
                gain = round((price - pos["entry_price"]) * pos["qty"], 2)
                state["capital"] = round(state["capital"] + pos["amount"] + gain, 2)
                state["trades"].append({
                    "symbol": symbol,
                    "name": pos["name"],
                    "entry_price": pos["entry_price"],
                    "exit_price": price,
                    "gain": gain,
                    "pct": round((gain / pos["amount"]) * 100, 2),
                    "time": now.isoformat(),
                    "result": "WIN" if gain > 0 else "LOSS",
                })
                print(f"  -> POSITION FERMEE: {gain:.2f} EUR sur {symbol} ({('WIN' if gain > 0 else 'LOSS')})")
            else:
                remaining.append(pos)
        state["positions"] = [p for p in state["positions"] if p["symbol"] != symbol] + \
                              [p for p in remaining if p["symbol"] == symbol]

    state["signals"] = signals
    state["last_update"] = now.isoformat()
    state["has_news_warning"] = has_news
    state["news_event"] = news_event

    save_state(state)
    print("=== Mise a jour terminee ===")


if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        import traceback
        print("ERREUR FATALE:")
        print(traceback.format_exc())
        raise
