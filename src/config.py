"""
Zentrale Konfiguration für den Crypto Signal Bot.
Hier änderst du Einstellungen, ohne den restlichen Code anfassen zu müssen.
"""

import os

# --- Coin-Auswahl ---
TOP_N_COINS = 150          # Wie viele Coins nach Marktkapitalisierung beobachtet werden
QUOTE_CURRENCY = "USDT"    # Handelspaar-Basis auf Binance

# --- Kursdaten ---
TIMEFRAME = "4h"           # Kerzenintervall: 1h, 4h, 1d ...
CANDLE_LIMIT = 100         # Anzahl der Kerzen, die für die Analyse geladen werden

# --- Indikator-Schwellwerte ---
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOLUME_SPIKE_FACTOR = 1.8   # Volumen X-mal über dem Durchschnitt der letzten 20 Kerzen
EMA_FAST = 20
EMA_SLOW = 50

# --- News ---
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]
NEWS_LOOKBACK_HOURS = 6     # Nur News der letzten X Stunden berücksichtigen

POSITIVE_KEYWORDS = [
    "surge", "rally", "bullish", "breakout", "adoption", "partnership",
    "upgrade", "approval", "etf approved", "record high", "buy", "inflow",
    "integration", "listing", "positive", "soar", "pump"
]
NEGATIVE_KEYWORDS = [
    "crash", "bearish", "sell-off", "selloff", "hack", "exploit", "lawsuit",
    "ban", "regulation crackdown", "delist", "outflow", "dump", "plunge",
    "investigation", "fraud", "collapse", "negative"
]

# Namen einflussreicher Personen/Institutionen, deren Aussagen den Markt
# stark bewegen können. Wird in News-Artikeln gesucht (Titel + Zusammenfassung).
# Hinweis: Kein Live-Zugriff auf X/Twitter selbst (kostenpflichtige API) -
# basiert auf Berichterstattung durch die konfigurierten Krypto-News-Seiten,
# die solche Aussagen meist innerhalb weniger Stunden aufgreifen.
INFLUENCER_KEYWORDS = [
    "trump", "elon musk", "musk", "sec chair", "jerome powell", "powell",
    "gary gensler", "gensler", "michael saylor", "saylor", "changpeng zhao",
    "cz binance", "vitalik buterin", "blackrock", "larry fink",
]
NEWS_DEDUP_HOURS = 48  # verhindert, dass derselbe Artikel mehrfach gemeldet wird

# --- Benachrichtigung (ntfy.sh) ---
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # wird als GitHub Secret gesetzt
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Nur Signale ab dieser Stufe werden als Push-Nachricht verschickt.
# Stufe 2 = mehrere Indikatoren bestätigen sich gegenseitig JETZT, OHNE
# dass der Kurs sich schon merklich bewegt haben muss (das wäre erst
# Stufe 3). Kommt seltener vor als Stufe 1, dafür mit höherer Sicherheit -
# genau der Kompromiss zwischen "früh genug" und "zuverlässig genug".
NOTIFY_MIN_TIER = 2

# --- Erfolgs-Auswertung ---
# Nach wie vielen Stunden wird geprüft, ob ein Signal "richtig" lag?
OUTCOME_CHECK_HOURS = 12
# Ab welcher prozentualen Kursbewegung (in die vorhergesagte Richtung)
# gilt ein Signal als "richtig" (statt "neutral/unklar")?
OUTCOME_MOVE_THRESHOLD_PCT = 1.0
SIGNAL_HISTORY_FILE = "data/signal_history.json"
FAILURE_PATTERNS_FILE = "data/failure_patterns.json"

# --- State / Dedup ---
STATE_FILE = "data/state.json"
# Wie lange (in Stunden) ein Coin nach einer Meldung "stumm" bleibt,
# bevor er auf DERSELBEN Stufe erneut melden darf
COOLDOWN_HOURS = {
    1: 12,
    2: 6,
    3: 2,
}
