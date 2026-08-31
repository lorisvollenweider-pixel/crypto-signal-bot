"""
Speichert jedes gefundene Signal mit Preis+Zeitstempel und prüft nach
einer festgelegten Wartezeit (config.OUTCOME_CHECK_HOURS) automatisch,
ob sich der Kurs tatsächlich in die vorhergesagte Richtung bewegt hat.

So bekommst du ohne eigenes Zutun eine ehrliche Trefferquote des Bots,
statt nur die rohen Signale ohne Kontext.
"""

import json
import os
from datetime import datetime, timezone

from src import config, data_fetcher


def load_history() -> list[dict]:
    if not os.path.exists(config.SIGNAL_HISTORY_FILE):
        return []
    try:
        with open(config.SIGNAL_HISTORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_history(history: list[dict]):
    os.makedirs(os.path.dirname(config.SIGNAL_HISTORY_FILE), exist_ok=True)
    with open(config.SIGNAL_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_signal(history: list[dict], signal: dict, kucoin_symbol: str):
    """Fügt ein neu gefundenes Signal der Historie hinzu (für spätere Auswertung)."""
    history.append({
        "symbol": signal["symbol"],
        "kucoin_symbol": kucoin_symbol,
        "direction": signal["direction"],
        "tier": signal["tier"],
        "price_at_signal": signal["price"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checked": False,
        "outcome": None,
        "change_pct": None,
    })


def evaluate_due_signals(history: list[dict]) -> list[dict]:
    """
    Prüft alle Signale, die alt genug sind (OUTCOME_CHECK_HOURS) und noch
    nicht ausgewertet wurden. Holt den aktuellen Preis und bestimmt, ob
    das Signal "richtig", "falsch" oder "neutral" (kaum Bewegung) war.
    Gibt die Liste der gerade neu ausgewerteten Einträge zurück.
    """
    now = datetime.now(timezone.utc)
    newly_evaluated = []

    for entry in history:
        if entry["checked"]:
            continue

        signal_time = datetime.fromisoformat(entry["timestamp"])
        age_hours = (now - signal_time).total_seconds() / 3600
        if age_hours < config.OUTCOME_CHECK_HOURS:
            continue

        current_price = data_fetcher.get_current_price(entry["kucoin_symbol"])
        if current_price is None:
            continue  # später nochmal versuchen

        price_then = entry["price_at_signal"]
        change_pct = (current_price - price_then) / price_then * 100

        threshold = config.OUTCOME_MOVE_THRESHOLD_PCT
        if entry["direction"] == "long":
            outcome = "richtig" if change_pct >= threshold else (
                "falsch" if change_pct <= -threshold else "neutral")
        else:  # short
            outcome = "richtig" if change_pct <= -threshold else (
                "falsch" if change_pct >= threshold else "neutral")

        entry["checked"] = True
        entry["outcome"] = outcome
        entry["change_pct"] = round(change_pct, 2)
        newly_evaluated.append(entry)

    return newly_evaluated


def prune_old_history(history: list[dict], max_age_days: int = 14) -> list[dict]:
    """Entfernt sehr alte, bereits ausgewertete Einträge, damit die Datei nicht endlos wächst."""
    now = datetime.now(timezone.utc)
    kept = []
    for entry in history:
        signal_time = datetime.fromisoformat(entry["timestamp"])
        age_days = (now - signal_time).total_seconds() / 86400
        if age_days < max_age_days or not entry["checked"]:
            kept.append(entry)
    return kept
