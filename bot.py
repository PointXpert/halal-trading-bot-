"""
HalalBot v2 - Connecte a Trading 212
100% halal - Scanner universel - Reversal + RSI + MM
"""
import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

T212_API_KEY = os.environ.get("T212_API_KEY", "")
T212_SECRET = os.environ.get("T212_SECRET", "")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")

DATA_FILE = "data/state.json"
INITIAL_CAPITAL = 1000.0
RISK_PER_TRADE = 0.20
MAX_POSITION = 200.0

T212_BASE = "https://live.trading212.com/api/v0"

HALAL_TICKERS = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "ASML", "LLY",
    "AMD", "AVGO", "TSM", "ORCL", "ADBE", "CRM", "QCOM", "TXN",
    "INTC", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "CDNS", "SNPS",
    "NOW", "WDAY", "DDOG", "ZS", "CRWD", "PANW", "FTNT",
    "UNH", "JNJ", "ABT", "MDT", "SYK", "BSX", "EW", "ISRG",
    "PFE", "MRK", "LLY", "ABBV", "AMGN", "GILD", "REGN", "VRTX",
    "XOM", "CVX", "COP", "EOG", "PXD", "SLB", "HAL", "BKR",
    "GEV", "NEE", "AEP", "XEL", "CCJ", "NEM", "GOLD",
    "COST", "WMT", "TGT", "HD", "LOW", "NKE", "SBUX",
    "BA", "CAT", "DE", "HON", "GE", "MMM", "ITW", "EMR",
    "NOK", "ERIC", "TMUS", "VZ", "CSCO", "ANET", "JNPR",
}


def t212_headers():
    return {
        "Authorization": T212_API_KEY,
        "Content-Type": "application/json"
    }


def get_t212_positions():
    try:
        r = requests.get(
            f"{T212_BASE}/equity/portfolio",
            headers=t212_headers(),
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        print(f"T212 portfolio error: {r.status_code}")
        return []
    except Exception as e:
        print(f"Erreur T212 portfolio: {e}")
        return []


def get_t212_cash():
    try:
        r = requests.get(
            f"{T212_BASE}/equity/account/cash",
            headers=t212_headers(),
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return float(data.get("free", 0))
        print(f"T212 cash error: {r.status_code}")
        return None
    except Exception as e:
        print(f"Erreur T212 cash: {e}")
        return None


def get_t212_instruments():
    try:
        r = requests.get(
            f"{T212_BASE}/equity/metadata/instruments",
            headers=t212_headers(),
            timeout=15
        )
        if r.status_code == 200:
            instruments = r.json()
            halal = [
                i for i in instruments
                if i.get("ticker", "").upper() in HALAL_TICKERS
            ]
            print(f"Instruments halal trouves sur T212: {len(halal)}")
            return halal
        print(f"T212 instruments error: {r.status_code}")
        return []
    except Exception as e:
        print(f"Erreur T212 instruments: {e}")
        return []


def get_t212_price(ticker):
    try:
        r = requests.get(
            f"{T212_BASE}/equity/metadata/instruments",
            headers=t212_headers(),
            timeout=10
        )
        if r.status_code == 200:
            instruments = r.json()
            for inst in instruments:
                if inst.get("ticker", "").upper() == ticker.upper():
                    return float(inst.get("currentPrice", 0)) or None
        return None
    except Exception as e:
        print(f"Erreur prix T212 {ticker}: {e}")
        return None


def place_t212_order(ticker, value_eur):
    try:
        payload = {
            "ticker": ticker,
            "value": round(value_eur, 2),
            "timeValidity": "DAY"
        }
        r = requests.post(
            f"{T212_BASE}/equity/orders/market",
            headers=t212_headers(),
            json=payload,
            timeout=10
        )
        if r.status_code in [200, 201]:
            print(f"  -> ORDRE T212 PLACE: {value_eur}EUR sur {ticker}")
            return r.json()
        print(f"  -> ERREUR ORDRE T212 {ticker}: {r.status_code} {r.text}")
        return None
    except Exception as e:
        print(f"Erreur ordre T212 {ticker}: {e}")
        return None


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


def get_alpha_price(symbol):
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
        print(f"Erreur Alpha {symbol}: {e}")
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
            r = requests.get(
                url, timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if r.status_code != 200:
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


def calculate_rsi(history, period=14):
    if len(history) < period + 1:
        return None
    gains = []
    losses = []
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
    if avg_loss == 0:
        avg_loss = 0.0001
    if avg_gain == 0:
        avg_gain = 0.0001
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

    if rsi is not None and rsi < 30 and below_ma:
        return "REVERSAL HAUSSIER", f"RSI survente {rsi_label} retournement probable"

    if rsi is not None and rsi > 70 and above_ma:
        return "REVERSAL BAISSIER", f"RSI surachat {rsi_label} correction probable"

    if above_ma and rsi_ok_buy:
        return "ACHETER", f"Prix au-dessus MM10, {rsi_label}"
    elif below_ma and rsi_ok_sell:
        return "VENDRE", f"Prix sous MM10, {rsi_label}"
    else:
        return "ATTENDRE", f"Pas de signal clair, {rsi_label}"


def load_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "capital": INITIAL_CAPITAL,
        "positions": [],
        "trades": [],
        "price_history": {},
        "last_update": None,
        "mode": "paper"
    }


def save_state(state):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_bot():
    state = load_state()
    now = datetime.now(timezone.utc)
    print(f"=== HalalBot v2 - {now.isoformat()} ===")

    has_news, news_event = get_high_impact_news()
    if has_news:
        print(f"News a fort impact: {news_event}")
    else:
        print("Pas de news a fort impact")

    cash_t212 = get_t212_cash()
    if cash_t212 is not None:
        print(f"Capital T212 reel: {cash_t212} EUR")
        state["capital_reel"] = cash_t212
    else:
        print("T212 non connecte - mode paper trading")

    instruments = get_t212_instruments()
    if not instruments:
        instruments = [
            {"ticker": t} for t in [
                "NVDA", "MSFT", "AAPL", "TSLA", "AMZN",
                "GOOGL", "LLY", "ASML", "AMD", "NOK"
            ]
        ]

    signals = {}
    best_signals = []

    for inst in instruments[:30]:
        ticker = inst.get("ticker", "").upper()
        if not ticker:
            continue

        price = None
        if ticker == "BTC":
            price = get_btc_price()
        else:
            price = get_alpha_price(ticker)
            if price is None:
                price = float(inst.get("currentPrice", 0)) or None

        if price is None or price == 0:
            continue

        history = state["price_history"].setdefault(ticker, [])
        history.append(price)
        state["price_history"][ticker] = history[-50:]

        signal, reason = analyze_signal(ticker, price, history)
        signals[ticker] = {"signal": signal, "reason": reason, "price": price}
        print(f"{ticker}: {price} -> {signal} ({reason})")

        if signal in ["ACHETER", "REVERSAL HAUSSIER"] and not has_news:
            already_open = any(
                p["symbol"] == ticker for p in state["positions"]
            )
            if not already_open:
                best_signals.append({
                    "ticker": ticker,
                    "price": price,
                    "signal": signal,
                    "reason": reason
                })

        time.sleep(1)

    best_signals.sort(
        key=lambda x: 0 if x["signal"] == "REVERSAL HAUSSIER" else 1
    )

    for sig in best_signals[:3]:
        ticker = sig["ticker"]
        price = sig["price"]
        signal = sig["signal"]

        if state["capital"] < 100:
            break

        amount = min(state["capital"] * RISK_PER_TRADE, MAX_POSITION)
        if signal == "REVERSAL HAUSSIER":
            amount = amount * 0.7

        qty = amount / price
        position = {
            "symbol": ticker,
            "name": ticker,
            "entry_price": price,
            "qty": qty,
            "amount": amount,
            "tp": round(price * 1.03, 2),
            "sl": round(price * 0.985, 2),
            "open_time": now.isoformat(),
            "strategy": signal,
        }

        if cash_t212 is not None and cash_t212 > amount:
            result = place_t212_order(ticker, amount)
            if result:
                state["positions"].append(position)
                state["capital"] = round(state["capital"] - amount, 2)
                print(f"  -> ORDRE REEL: {amount}EUR sur {ticker} ({signal})")
        else:
            state["positions"].append(position)
            state["capital"] = round(state["capital"] - amount, 2)
            print(f"  -> PAPER TRADE: {amount}EUR sur {ticker} ({signal})")

    remaining = []
    for pos in state["positions"]:
        ticker = pos["symbol"]
        sig = signals.get(ticker)
        if sig is None:
            remaining.append(pos)
            continue
        price = sig["price"]
        if price >= pos["tp"] or price <= pos["sl"]:
            gain = round((price - pos["entry_price"]) * pos["qty"], 2)
            state["capital"] = round(
                state["capital"] + pos["amount"] + gain, 2
            )
            state["trades"].append({
                "symbol": ticker,
                "name": pos["name"],
                "entry_price": pos["entry_price"],
                "exit_price": price,
                "gain": gain,
                "pct": round((gain / pos["amount"]) * 100, 2),
                "time": now.isoformat(),
                "result": "WIN" if gain > 0 else "LOSS",
                "strategy": pos.get("strategy", "ACHETER"),
            })
            print(f"  -> FERME: {gain}EUR sur {ticker}")
        else:
            remaining.append(pos)

    state["positions"] = remaining
    state["signals"] = signals
    state["last_update"] = now.isoformat()
    state["has_news_warning"] = has_news
    state["news_event"] = news_event

    save_state(state)
    print("=== HalalBot v2 termine ===")


if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        import traceback
        print("ERREUR FATALE:")
        print(traceback.format_exc())
        raise
