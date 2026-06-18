"""
HalalBot - Bot de paper trading avec vraies données de marché
100% halal - Sans intérêts, sans levier, sans CFD
"""
import os
import json
import time
import requests
from datetime import datetime, timezone

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

DATA_FILE = "data/state.json"

INSTRUMENTS = {
    "XAUUSD": {"name": "Or / Gold", "type": "commodity", "symbol": "XAU"},
    "BTC": {"name": "Bitcoin", "type": "crypto", "symbol": "bitcoin"},
    "NVDA": {"name": "Nvidia", "type": "stock", "symbol": "NVDA"},
    "MSFT": {"name": "Microsoft", "type": "stock", "symbol": "MSFT"},
    "AAPL": {"name": "Apple", "type": "stock", "symbol": "AAPL"},
    "TSLA": {"name": "Tesla", "type": "stock", "symbol": "TSLA"},
        "AMZN": {"name": "Amazon", "type": "stock", "symbol": "AMZN"},


