"""
Verwaltet den gespeicherten Zustand zwischen den Läufen, damit nicht bei
jedem Durchlauf (alle 15 Min) dieselbe Meldung erneut gesendet wird.

Der Zustand wird als JSON-Datei im Repo gespeichert und von der
GitHub Action nach jedem Lauf automatisch zurück committed.
"""

import json
import os
from datetime import datetime, timezone

from src import config


def load_state() -> dict:
    if not os.path.exists(config.STATE_FILE):
        return {}
    try:
        with open(config.STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_state(state: dict):
    os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def should_notify(state: dict, signal: dict) -> bool:
    """Prüft, ob für dieses Signal (Coin+Richtung+Stufe) der Cooldown abgelaufen ist."""
    key = f"{signal['symbol']}_{signal['direction']}_{signal['tier']}"
    entry = state.get(key)
    cooldown_hours = config.COOLDOWN_HOURS.get(signal["tier"], 6)

    if entry is None:
        return True

    last_sent = datetime.fromisoformat(entry["last_sent"])
    elapsed_hours = (datetime.now(timezone.utc) - last_sent).total_seconds() / 3600
    return elapsed_hours >= cooldown_hours


def mark_notified(state: dict, signal: dict):
    key = f"{signal['symbol']}_{signal['direction']}_{signal['tier']}"
    state[key] = {"last_sent": datetime.now(timezone.utc).isoformat()}
