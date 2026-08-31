"""
Technische Analyse: berechnet Indikatoren und leitet daraus ein
Konfidenz-Signal ab (Richtung + Stufe 1/2/3).

WICHTIG: Das sind statistische Wahrscheinlichkeiten basierend auf
historischen Mustern - KEINE Vorhersagen und KEINE Garantien.
"""

import pandas as pd
import pandas_ta as ta

from src import config


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Fügt technische Indikatoren als Spalten zum DataFrame hinzu."""
    df = df.copy()
    df["rsi"] = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"])
    if macd is not None:
        df = pd.concat([df, macd], axis=1)
    bbands = ta.bbands(df["close"], length=20)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)
    df["ema_fast"] = ta.ema(df["close"], length=config.EMA_FAST)
    df["ema_slow"] = ta.ema(df["close"], length=config.EMA_SLOW)
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    return df


def _find_col(df: pd.DataFrame, prefix: str) -> str | None:
    """Hilfsfunktion: findet die tatsächliche Spaltenbezeichnung von pandas-ta."""
    matches = [c for c in df.columns if c.startswith(prefix)]
    return matches[0] if matches else None


def _find_local_extrema(values, order: int = 3) -> tuple[list[int], list[int]]:
    """
    Findet lokale Hoch- und Tiefpunkte in einer Preis-Reihe (einfache
    Fensterbetrachtung, kein externes Paket nötig).
    Gibt (Indizes der Hochpunkte, Indizes der Tiefpunkte) zurück.
    """
    highs_idx, lows_idx = [], []
    n = len(values)
    for i in range(order, n - order):
        window = values[i - order:i + order + 1]
        if values[i] == window.max() and values[i] != window.min():
            highs_idx.append(i)
        if values[i] == window.min() and values[i] != window.max():
            lows_idx.append(i)
    return _merge_close_indices(highs_idx, order), _merge_close_indices(lows_idx, order)


def _merge_close_indices(idx_list: list[int], min_gap: int) -> list[int]:
    """Fasst nahe beieinanderliegende Indizes (Plateaus) zu einem Punkt zusammen."""
    if not idx_list:
        return []
    merged = [idx_list[0]]
    for idx in idx_list[1:]:
        if idx - merged[-1] > min_gap:
            merged.append(idx)
    return merged


def detect_double_top_bottom(df: pd.DataFrame, lookback: int = 40) -> tuple[bool, bool]:
    """
    Prüft die letzten `lookback` Kerzen auf ein Double-Top- (bearish) oder
    Double-Bottom-Muster (bullish): zwei ungefähr gleich hohe Hoch-/Tiefpunkte
    mit einem deutlichen Gegenausschlag dazwischen, aktuell noch "frisch".
    Gibt (double_top_gefunden, double_bottom_gefunden) zurück.
    """
    recent = df.tail(lookback).reset_index(drop=True)
    if len(recent) < 20:
        return False, False

    highs_idx, lows_idx = _find_local_extrema(recent["high"].values, order=3)
    _, lows_idx_for_bottom = _find_local_extrema(recent["low"].values, order=3)

    double_top = False
    double_bottom = False
    n = len(recent)

    # --- Double Top: zwei ähnliche Hochpunkte, Tal dazwischen, aktuell nahe dran ---
    if len(highs_idx) >= 2:
        i1, i2 = highs_idx[-2], highs_idx[-1]
        p1, p2 = recent["high"].iloc[i1], recent["high"].iloc[i2]
        if abs(p1 - p2) / p1 * 100 <= 1.5 and (n - 1 - i2) <= 10:
            trough = recent["low"].iloc[i1:i2 + 1].min()
            drop_pct = (p1 - trough) / p1 * 100
            if drop_pct >= 2.0:
                double_top = True

    # --- Double Bottom: zwei ähnliche Tiefpunkte, Zwischenhoch, aktuell nahe dran ---
    if len(lows_idx_for_bottom) >= 2:
        i1, i2 = lows_idx_for_bottom[-2], lows_idx_for_bottom[-1]
        p1, p2 = recent["low"].iloc[i1], recent["low"].iloc[i2]
        if abs(p1 - p2) / p1 * 100 <= 1.5 and (n - 1 - i2) <= 10:
            peak = recent["high"].iloc[i1:i2 + 1].max()
            rise_pct = (peak - p1) / p1 * 100
            if rise_pct >= 2.0:
                double_bottom = True

    return double_top, double_bottom


def analyze_coin(symbol: str, df: pd.DataFrame) -> dict | None:
    """
    Analysiert einen Coin und gibt ein Signal-Dict zurück:
    {
        symbol, direction ("long"/"short"), tier (1-3),
        reasons: [...], price, rsi, ...
    }
    Gibt None zurück, wenn kein relevantes Signal vorliegt.
    """
    if len(df) < 30:
        return None

    df = compute_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    bullish_points = []
    bearish_points = []

    # --- RSI ---
    if pd.notna(latest["rsi"]):
        if latest["rsi"] < config.RSI_OVERSOLD:
            bullish_points.append(f"RSI überverkauft ({latest['rsi']:.1f})")
        elif latest["rsi"] > config.RSI_OVERBOUGHT:
            bearish_points.append(f"RSI überkauft ({latest['rsi']:.1f})")

    # --- MACD Crossover ---
    macd_col = _find_col(df, "MACD_")
    signal_col = _find_col(df, "MACDs_")
    if macd_col and signal_col and pd.notna(latest[macd_col]) and pd.notna(prev[macd_col]):
        crossed_up = prev[macd_col] < prev[signal_col] and latest[macd_col] > latest[signal_col]
        crossed_down = prev[macd_col] > prev[signal_col] and latest[macd_col] < latest[signal_col]
        if crossed_up:
            bullish_points.append("MACD Bullish Crossover")
        if crossed_down:
            bearish_points.append("MACD Bearish Crossover")

    # --- EMA Trend ---
    if pd.notna(latest["ema_fast"]) and pd.notna(latest["ema_slow"]):
        if latest["ema_fast"] > latest["ema_slow"] and prev["ema_fast"] <= prev["ema_slow"]:
            bullish_points.append(f"EMA{config.EMA_FAST} kreuzt EMA{config.EMA_SLOW} von unten")
        elif latest["ema_fast"] < latest["ema_slow"] and prev["ema_fast"] >= prev["ema_slow"]:
            bearish_points.append(f"EMA{config.EMA_FAST} kreuzt EMA{config.EMA_SLOW} von oben")

    # --- Bollinger Bands (Ausbruch) ---
    bb_lower = _find_col(df, "BBL_")
    bb_upper = _find_col(df, "BBU_")
    if bb_lower and bb_upper and pd.notna(latest[bb_lower]):
        if latest["close"] < latest[bb_lower]:
            bullish_points.append("Preis unter unterem Bollinger Band")
        elif latest["close"] > latest[bb_upper]:
            bearish_points.append("Preis über oberem Bollinger Band")

    # --- Volumen-Spike ---
    vol_spike = False
    if pd.notna(latest["vol_avg20"]) and latest["vol_avg20"] > 0:
        if latest["volume"] > latest["vol_avg20"] * config.VOLUME_SPIKE_FACTOR:
            vol_spike = True
            direction_hint = "bullish" if latest["close"] > latest["open"] else "bearish"
            if direction_hint == "bullish":
                bullish_points.append(f"Volumen-Spike ({latest['volume']/latest['vol_avg20']:.1f}x Durchschnitt)")
            else:
                bearish_points.append(f"Volumen-Spike ({latest['volume']/latest['vol_avg20']:.1f}x Durchschnitt)")

    # --- Chart-Pattern: Double Top / Double Bottom ---
    double_top, double_bottom = detect_double_top_bottom(df)
    if double_top:
        bearish_points.append("Double-Top-Formation erkannt")
    if double_bottom:
        bullish_points.append("Double-Bottom-Formation erkannt")

    # --- Preisbewegung bereits im Gange? (für Stufe 3) ---
    recent_change_pct = (latest["close"] - df.iloc[-4]["close"]) / df.iloc[-4]["close"] * 100

    # --- Richtung bestimmen ---
    if len(bullish_points) == 0 and len(bearish_points) == 0:
        return None

    if len(bullish_points) > len(bearish_points):
        direction = "long"
        reasons = bullish_points
        score = len(bullish_points)
    elif len(bearish_points) > len(bullish_points):
        direction = "short"
        reasons = bearish_points
        score = len(bearish_points)
    else:
        return None  # keine klare Richtung

    # --- Stufe (Tier) bestimmen ---
    already_moving = (direction == "long" and recent_change_pct > 3) or \
                      (direction == "short" and recent_change_pct < -3)

    if already_moving and score >= 2:
        tier = 3  # Bewegung läuft bereits, mehrere Indikatoren bestätigen
    elif score >= 3:
        tier = 2  # mehrere Indikatoren stimmen überein
    elif score >= 1:
        tier = 1  # erstes schwaches Signal
    else:
        return None

    # --- Stop-Loss / Take-Profit (ATR-basiert) ---
    # Orientierung, keine Vorhersage: nutzt die jüngste Schwankungsbreite
    # (ATR) des Coins, um einen vernünftigen Risiko-Rahmen zu setzen.
    # Chance-Risiko-Verhältnis ca. 1:2 (Take-Profit-Distanz = 2x Stop-Loss-Distanz)
    stop_loss = None
    take_profit = None
    if pd.notna(latest["atr"]) and latest["atr"] > 0:
        atr = latest["atr"]
        price = latest["close"]
        if direction == "long":
            stop_loss = price - 1.5 * atr
            take_profit = price + 3.0 * atr
        else:
            stop_loss = price + 1.5 * atr
            take_profit = price - 3.0 * atr

    return {
        "symbol": symbol,
        "direction": direction,
        "tier": tier,
        "reasons": reasons,
        "price": latest["close"],
        "rsi": round(latest["rsi"], 1) if pd.notna(latest["rsi"]) else None,
        "recent_change_pct": round(recent_change_pct, 2),
        "volume_spike": vol_spike,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
    }


def analyze_all(klines: dict[str, pd.DataFrame]) -> list[dict]:
    """Analysiert alle Coins und gibt eine Liste gefundener Signale zurück."""
    signals = []
    for symbol, df in klines.items():
        try:
            result = analyze_coin(symbol, df)
            if result:
                signals.append(result)
        except Exception:
            # Ein fehlerhafter Coin soll nicht den ganzen Lauf abbrechen
            continue
    return signals
