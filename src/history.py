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
        "reasons": signal.get("reasons", []),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checked": False,
        "outcome": None,
        "change_pct": None,
        # Beste bisher erreichte Bewegung IN VORHERGESAGTE RICHTUNG (in %),
        # wird bei jedem Lauf aktualisiert - erfasst auch kurze Ausschläge,
        # die zum Zeitpunkt der finalen Prüfung schon wieder vorbei wären.
        "best_favorable_pct": 0.0,
    })


def update_open_signals(history: list[dict]):
    """
    Aktualisiert bei jedem Lauf die 'beste erreichte Bewegung' aller noch
    offenen (nicht ausgewerteten) Signale. So zählt eine Bewegung, die
    zwischendurch (z.B. nach 6h) das Ziel erreicht hatte, auch dann noch,
    wenn der Kurs bis zur finalen 12h-Prüfung wieder zurückgegangen ist.
    """
    for entry in history:
        if entry["checked"]:
            continue
        current_price = data_fetcher.get_current_price(entry["kucoin_symbol"])
        if current_price is None:
            continue

        price_then = entry["price_at_signal"]
        raw_change_pct = (current_price - price_then) / price_then * 100
        # "favorable" = positiv, wenn Bewegung in die vorhergesagte Richtung ging
        favorable_pct = raw_change_pct if entry["direction"] == "long" else -raw_change_pct

        if favorable_pct > entry.get("best_favorable_pct", 0.0):
            entry["best_favorable_pct"] = round(favorable_pct, 2)


def evaluate_due_signals(history: list[dict]) -> list[dict]:
    """
    Prüft alle Signale, die alt genug sind (OUTCOME_CHECK_HOURS) und noch
    nicht ausgewertet wurden. Nutzt die während der gesamten Wartezeit
    verfolgte beste Kursbewegung (siehe update_open_signals), nicht nur
    eine einzelne Momentaufnahme am Ende - ein kurzer Dip vor dem
    eigentlichen Anstieg zählt also nicht automatisch als "falsch".
    Gibt die Liste der gerade neu ausgewerteten Einträge zurück.
    """
    now = datetime.now(timezone.utc)
    newly_evaluated = []
    threshold = config.OUTCOME_MOVE_THRESHOLD_PCT

    for entry in history:
        if entry["checked"]:
            continue

        signal_time = datetime.fromisoformat(entry["timestamp"])
        age_hours = (now - signal_time).total_seconds() / 3600
        if age_hours < config.OUTCOME_CHECK_HOURS:
            continue

        # Finalen aktuellen Preis noch einmal einbeziehen, falls er gerade
        # jetzt erst den Zielwert erreicht (letzter Datenpunkt im Fenster)
        current_price = data_fetcher.get_current_price(entry["kucoin_symbol"])
        best_favorable_pct = entry.get("best_favorable_pct", 0.0)
        if current_price is not None:
            price_then = entry["price_at_signal"]
            raw_change_pct = (current_price - price_then) / price_then * 100
            favorable_pct = raw_change_pct if entry["direction"] == "long" else -raw_change_pct
            best_favorable_pct = max(best_favorable_pct, favorable_pct)

        if best_favorable_pct >= threshold:
            outcome = "richtig"
        elif best_favorable_pct <= -threshold:
            outcome = "falsch"
        else:
            outcome = "neutral"

        entry["checked"] = True
        entry["outcome"] = outcome
        entry["change_pct"] = round(best_favorable_pct, 2)
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


def analyze_failure_patterns(history: list[dict], min_samples: int = 3) -> list[dict]:
    """
    Schaut sich alle bereits ausgewerteten Signale an und gruppiert sie nach
    dem jeweiligen Grund/Indikator (z.B. "Double-Top-Formation erkannt").
    So wird sichtbar, welche Indikatoren häufiger zu falschen Signalen
    führen als andere - eine Art Selbstkritik-Bericht des Bots.

    Läuft rein auf bereits gespeicherten Daten (keine neuen API-Aufrufe
    nötig), kann also bei jedem Lauf günstig mitlaufen.

    Gibt eine nach Trefferquote sortierte Liste zurück:
    [{"reason": "...", "richtig": n, "falsch": n, "neutral": n,
      "accuracy_pct": n, "total": n}, ...]
    """
    stats: dict[str, dict[str, int]] = {}

    for entry in history:
        if not entry.get("checked"):
            continue
        outcome = entry.get("outcome")
        if outcome is None:
            continue
        for reason in entry.get("reasons", []):
            # Zahlen aus dem Grund entfernen (z.B. "RSI überkauft (91.1)" ->
            # "RSI überkauft"), damit ähnliche Gründe zusammengefasst werden
            base_reason = reason.split("(")[0].strip()
            if base_reason not in stats:
                stats[base_reason] = {"richtig": 0, "falsch": 0, "neutral": 0}
            stats[base_reason][outcome] += 1

    result = []
    for reason, counts in stats.items():
        total = counts["richtig"] + counts["falsch"] + counts["neutral"]
        if total < min_samples:
            continue  # zu wenig Datenpunkte für eine verlässliche Aussage
        decisive = counts["richtig"] + counts["falsch"]
        accuracy_pct = round(counts["richtig"] / decisive * 100, 1) if decisive > 0 else None
        result.append({
            "reason": reason,
            "richtig": counts["richtig"],
            "falsch": counts["falsch"],
            "neutral": counts["neutral"],
            "total": total,
            "accuracy_pct": accuracy_pct,
        })

    # Schlechteste Trefferquote zuerst (das Interessanteste für Selbstkritik)
    result.sort(key=lambda r: (r["accuracy_pct"] is None, r["accuracy_pct"]))
    return result


def save_failure_patterns(patterns: list[dict]):
    os.makedirs(os.path.dirname(config.FAILURE_PATTERNS_FILE), exist_ok=True)
    with open(config.FAILURE_PATTERNS_FILE, "w") as f:
        json.dump(patterns, f, indent=2)
