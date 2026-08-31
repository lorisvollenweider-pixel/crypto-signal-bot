"""
Holt die Top-Coins (CoinGecko) und deren Kursdaten (Binance Public API).
Beide APIs sind kostenlos und benötigen keinen API-Key.
"""

import time
import requests
import pandas as pd

from src import config

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"

TIMEFRAME_TO_BINANCE = {
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def get_top_coins(limit: int = None) -> list[dict]:
    """Holt die Top-Coins nach Marktkapitalisierung von CoinGecko."""
    limit = limit or config.TOP_N_COINS
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": min(limit, 250),
        "page": 1,
        "sparkline": "false",
    }
    resp = requests.get(COINGECKO_URL, params=params, timeout=20)
    resp.raise_for_status()
    coins = resp.json()
    return [
        {"id": c["id"], "symbol": c["symbol"].upper(), "name": c["name"],
         "market_cap_rank": c.get("market_cap_rank")}
        for c in coins
    ]


def get_binance_symbols() -> set[str]:
    """Liste aller aktiven USDT-Handelspaare auf Binance."""
    resp = requests.get(BINANCE_EXCHANGE_INFO_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return {
        s["symbol"] for s in data["symbols"]
        if s["quoteAsset"] == config.QUOTE_CURRENCY and s["status"] == "TRADING"
    }


def get_klines(symbol: str, interval: str = None, limit: int = None) -> pd.DataFrame | None:
    """Holt Kerzendaten (OHLCV) für ein Handelspaar von Binance."""
    interval = TIMEFRAME_TO_BINANCE.get(interval or config.TIMEFRAME, "4h")
    limit = limit or config.CANDLE_LIMIT
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = requests.get(BINANCE_KLINES_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        raw = resp.json()
        if not raw:
            return None
        df = pd.DataFrame(raw, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df
    except requests.RequestException:
        return None


def build_watchlist() -> list[dict]:
    """
    Kombiniert Top-Coins von CoinGecko mit verfügbaren Binance-Symbolen.
    Gibt eine Liste von {id, symbol, name, binance_symbol} zurück.
    """
    coins = get_top_coins()
    binance_symbols = get_binance_symbols()

    watchlist = []
    for c in coins:
        pair = f"{c['symbol']}{config.QUOTE_CURRENCY}"
        if pair in binance_symbols:
            c["binance_symbol"] = pair
            watchlist.append(c)
    return watchlist


def fetch_all_klines(watchlist: list[dict]) -> dict[str, pd.DataFrame]:
    """Holt Kerzendaten für alle Coins der Watchlist. Respektiert Rate-Limits."""
    result = {}
    for i, coin in enumerate(watchlist):
        df = get_klines(coin["binance_symbol"])
        if df is not None and len(df) > 30:
            result[coin["symbol"]] = df
        # Binance erlaubt großzügige Rate-Limits, kleine Pause reicht
        if i % 20 == 0:
            time.sleep(0.5)
    return result
