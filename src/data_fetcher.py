"""
Holt die Top-Coins (CoinGecko) und deren Kursdaten (KuCoin Public API).
Beide APIs sind kostenlos und benötigen keinen API-Key.

Hinweis: Wir nutzen KuCoin statt Binance, weil Binance seine öffentliche
API für Server-Standorte in den USA sperrt (Fehler 451) - und genau dort
laufen die GitHub Actions Server. KuCoin hat diese Einschränkung nicht.
"""

import time
import requests
import pandas as pd

from src import config

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
KUCOIN_SYMBOLS_URL = "https://api.kucoin.com/api/v1/symbols"
KUCOIN_KLINES_URL = "https://api.kucoin.com/api/v1/market/candles"

TIMEFRAME_TO_KUCOIN = {
    "1h": "1hour",
    "4h": "4hour",
    "1d": "1day",
}

TIMEFRAME_SECONDS = {
    "1h": 3600,
    "4h": 4 * 3600,
    "1d": 24 * 3600,
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


def get_kucoin_symbols() -> set[str]:
    """Liste aller aktiven USDT-Handelspaare auf KuCoin."""
    resp = requests.get(KUCOIN_SYMBOLS_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return {
        s["symbol"] for s in data.get("data", [])
        if s.get("quoteCurrency") == config.QUOTE_CURRENCY and s.get("enableTrading")
    }


def get_klines(symbol: str, interval: str = None, limit: int = None) -> pd.DataFrame | None:
    """Holt Kerzendaten (OHLCV) für ein Handelspaar von KuCoin."""
    tf = interval or config.TIMEFRAME
    kucoin_type = TIMEFRAME_TO_KUCOIN.get(tf, "4hour")
    limit = limit or config.CANDLE_LIMIT
    seconds_per_candle = TIMEFRAME_SECONDS.get(tf, 4 * 3600)

    end_at = int(time.time())
    start_at = end_at - (limit * seconds_per_candle)

    params = {
        "symbol": symbol,
        "type": kucoin_type,
        "startAt": start_at,
        "endAt": end_at,
    }
    try:
        resp = requests.get(KUCOIN_KLINES_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        payload = resp.json()
        raw = payload.get("data", [])
        if not raw:
            return None

        # KuCoin liefert: [time, open, close, high, low, volume, turnover]
        # und die Liste ist neueste-zuerst -> wir drehen sie um (älteste-zuerst)
        raw = list(reversed(raw))
        df = pd.DataFrame(raw, columns=[
            "open_time", "open", "close", "high", "low", "volume", "turnover"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"].astype(float), unit="s")
        return df[["open_time", "open", "high", "low", "close", "volume"]]
    except requests.RequestException:
        return None


def build_watchlist() -> list[dict]:
    """
    Kombiniert Top-Coins von CoinGecko mit verfügbaren KuCoin-Symbolen.
    Gibt eine Liste von {id, symbol, name, kucoin_symbol} zurück.
    """
    coins = get_top_coins()
    kucoin_symbols = get_kucoin_symbols()

    watchlist = []
    for c in coins:
        pair = f"{c['symbol']}-{config.QUOTE_CURRENCY}"
        if pair in kucoin_symbols:
            c["kucoin_symbol"] = pair
            watchlist.append(c)
    return watchlist


def fetch_all_klines(watchlist: list[dict]) -> dict[str, pd.DataFrame]:
    """Holt Kerzendaten für alle Coins der Watchlist. Respektiert Rate-Limits."""
    result = {}
    for i, coin in enumerate(watchlist):
        df = get_klines(coin["kucoin_symbol"])
        if df is not None and len(df) > 30:
            result[coin["symbol"]] = df
        # kleine Pause, um KuCoins Rate-Limits nicht zu strapazieren
        if i % 15 == 0:
            time.sleep(0.5)
    return result
