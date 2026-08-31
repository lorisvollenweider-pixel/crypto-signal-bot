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


def _format_price(price: float) -> str:
    """Formatiert Preise mit genug Nachkommastellen, auch für sehr kleine Coins."""
    if price >= 1:
        return f"{price:.4f}"
    elif price >= 0.01:
        return f"{price:.6f}"
    else:
        return f"{price:.8f}"


def send_signal_notification(signal: dict, news_context: list[dict] = None):
    """Sendet eine Benachrichtigung für ein Trading-Signal (kompaktes Format)."""
    tier = signal["tier"]
    full_name = signal.get("full_name", "")
    tv_symbol = signal.get("tradingview_symbol", signal["symbol"])
    direction_emoji = "📈" if signal["direction"] == "long" else "📉"
    direction_word = "LONG" if signal["direction"] == "long" else "SHORT"

    name_display = f"{full_name} ({signal['symbol']})" if full_name else signal["symbol"]
    tier_short = {1: "Stufe 1", 2: "Stufe 2", 3: "Stufe 3"}[tier]
    title = f"{direction_emoji} {name_display} — {direction_word} — {tier_short}"

    lines = [
        f"💰 {_format_price(signal['price'])} USDT ({signal['recent_change_pct']:+.1f}%)",
        f"📊 TradingView: {tv_symbol}",
    ]

    if signal.get("stop_loss") is not None and signal.get("take_profit") is not None:
        sl = signal["stop_loss"]
        tp = signal["take_profit"]
        sl_pct = (sl - signal["price"]) / signal["price"] * 100
        tp_pct = (tp - signal["price"]) / signal["price"] * 100
        lines.append(f"🎯 SL: {_format_price(sl)} ({sl_pct:+.1f}%) | TP: {_format_price(tp)} ({tp_pct:+.1f}%)")
        lines.append("⏱️ Zeitrahmen: ca. 1-3 Tage (grobe Orientierung)")

    if tier == 3:
        lines.append("⚠️ Bewegung läuft evtl. schon - für Früheinstieg eher Stufe 2 beachten")

    lines.append("")
    lines.append("📌 " + " · ".join(signal["reasons"]))

    if news_context:
        top_news = news_context[0]
        sentiment_emoji = "🟢" if top_news["sentiment"] > 0 else "🔴"
        lines.append(f"{sentiment_emoji} News: {top_news['title']}")

    lines.append("")
    lines.append("Kein Finanzrat - eigene Prüfung nötig.")

    message = "\n".join(lines)
    _send(title, message, priority=TIER_PRIORITY[tier], tags=TIER_TAGS[tier])


def send_influencer_alert(entry: dict):
    """
    Sendet eine Warnung, wenn eine einflussreiche Person (z.B. Trump, Musk)
    in einer Krypto-News-Meldung erwähnt wird.
    """
    article = entry["article"]
    person = entry["matched_person"].title()
    coins = entry["matched_coins"]
    sentiment = entry["sentiment"]

    coins_str = ", ".join(coins) if coins else "kein spezifischer Coin erkannt"
    sentiment_word = "eher positiv" if sentiment > 0 else ("eher negativ" if sentiment < 0 else "neutral")

    title = f"🗣️ {person} erwähnt in Krypto-News"

    lines = [
        f"Betroffene Coins: {coins_str}",
        f"Einschätzung: {sentiment_word}",
        "",
        article["title"],
        "",
        f"Quelle: {article['source']}",
        article["link"],
        "",
        "Basiert auf News-Berichterstattung, nicht auf Live-X/Twitter-Zugriff.",
        "Kein Finanzrat - eigene Prüfung nötig.",
    ]

    message = "\n".join(lines)
    _send(title, message, priority="high", tags="loudspeaker")


def send_outcome_summary(evaluated: list[dict]):
    """
    Sendet EINE zusammenfassende Nachricht über kürzlich ausgewertete
    Signale (statt einer Einzelnachricht pro Coin) - zeigt, ob die
    Vorhersagen des Bots tatsächlich zugetroffen haben.
    """
    if not evaluated:
        return

    richtig = [e for e in evaluated if e["outcome"] == "richtig"]
    falsch = [e for e in evaluated if e["outcome"] == "falsch"]
    neutral = [e for e in evaluated if e["outcome"] == "neutral"]

    title = f"📊 Auswertung: {len(richtig)} richtig, {len(falsch)} falsch, {len(neutral)} neutral"

    lines = [f"{len(evaluated)} Signale von vor ~12h ausgewertet:", ""]
    for e in evaluated:
        symbol_marker = "✅" if e["outcome"] == "richtig" else ("❌" if e["outcome"] == "falsch" else "➖")
        direction_de = "LONG" if e["direction"] == "long" else "SHORT"
        lines.append(f"{symbol_marker} {e['symbol']} {direction_de}: {e['change_pct']:+.2f}%")

    lines.append("")
    lines.append("Kein Finanzrat - Trefferquote ist keine Garantie für die Zukunft.")

    message = "\n".join(lines)
    _send(title, message, priority="default", tags="bar_chart")


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
