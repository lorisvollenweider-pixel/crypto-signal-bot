"""
Versendet Push-Benachrichtigungen über ntfy.sh (kostenlos, kein Account nötig).
Installiere dazu die ntfy-App auf deinem Handy und abonniere dein Topic.
"""

import requests

from src import config

TIER_LABELS = {
    1: "Stufe 1 - Erstes Signal, beobachten",
    2: "Stufe 2 - Mehrere Indikatoren bestätigen",
    3: "Stufe 3 - Bewegung läuft bereits",
}

TIER_PRIORITY = {1: "default", 2: "high", 3: "urgent"}
TIER_TAGS = {1: "eyes", 2: "warning", 3: "rotating_light"}


def send_signal_notification(signal: dict, news_context: list[dict] = None):
    """Sendet eine Benachrichtigung für ein Trading-Signal."""
    direction_de = "LONG (steigend)" if signal["direction"] == "long" else "SHORT (fallend)"
    tier = signal["tier"]

    title = f"{signal['symbol']} – {direction_de} – {TIER_LABELS[tier]}"

    lines = [
        f"Preis: {signal['price']:.4f} USDT",
        f"Änderung (letzte 4 Kerzen): {signal['recent_change_pct']}%",
        "",
        "Gründe:",
    ]
    lines += [f"- {r}" for r in signal["reasons"]]

    if news_context:
        lines.append("")
        lines.append("Passende News:")
        for n in news_context[:2]:
            sentiment_word = "positiv" if n["sentiment"] > 0 else "negativ"
            lines.append(f"- ({sentiment_word}) {n['title']}")

    lines.append("")
    lines.append("Kein Finanzrat - eigene Prüfung nötig.")

    message = "\n".join(lines)
    _send(title, message, priority=TIER_PRIORITY[tier], tags=TIER_TAGS[tier])


def _send(title: str, message: str, priority: str = "default", tags: str = ""):
    if not config.NTFY_TOPIC:
        print("WARNUNG: NTFY_TOPIC nicht gesetzt, Benachrichtigung wird übersprungen.")
        print(title)
        print(message)
        return
    try:
        requests.post(
            config.NTFY_URL,
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": priority,
                "Tags": tags,
            },
            timeout=15,
        )
    except requests.RequestException as e:
        print(f"Fehler beim Senden der Benachrichtigung: {e}")


def send_run_summary(num_signals: int, num_coins_scanned: int, errors: int = 0):
    """Optionale kurze Zusammenfassung nach jedem Lauf (still, low priority)."""
    if num_signals == 0:
        return  # keine Nachricht, wenn nichts passiert ist - kein Spam
