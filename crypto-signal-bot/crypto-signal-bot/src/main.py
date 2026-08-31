"""
Hauptskript: Wird von der GitHub Action alle 15 Minuten ausgeführt.

Ablauf:
1. Top-Coins + Kursdaten laden
2. Technische Signale berechnen
3. Relevante News laden und Coins zuordnen
4. Cooldown/Dedup prüfen
5. Benachrichtigungen über ntfy.sh senden
6. Zustand speichern
"""

import sys
import time

from src import config, data_fetcher, indicators, news, notifier, state as state_module


def run():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starte Scan...")

    print("Lade Watchlist (Top Coins)...")
    watchlist = data_fetcher.build_watchlist()
    print(f"{len(watchlist)} Coins in Watchlist (mit Binance-Handelspaar).")

    if not watchlist:
        print("FEHLER: Keine Watchlist geladen, breche ab.")
        sys.exit(1)

    print("Lade Kursdaten...")
    klines = data_fetcher.fetch_all_klines(watchlist)
    print(f"Kursdaten für {len(klines)} Coins geladen.")

    print("Berechne technische Signale...")
    signals = indicators.analyze_all(klines)
    print(f"{len(signals)} Signale gefunden.")

    print("Lade News...")
    try:
        articles = news.fetch_recent_news()
        coin_news = news.match_coins_in_news(articles, watchlist)
        print(f"{len(articles)} News-Artikel geladen, {len(coin_news)} Coins mit relevanten News.")
    except Exception as e:
        print(f"News konnten nicht geladen werden: {e}")
        coin_news = {}

    print("Prüfe Cooldowns und sende Benachrichtigungen...")
    persisted_state = state_module.load_state()
    sent_count = 0

    for signal in signals:
        if state_module.should_notify(persisted_state, signal):
            relevant_news = coin_news.get(signal["symbol"])
            # News-Sentiment kann Signal zusätzlich stützen oder relativieren -
            # wird hier nur als Kontext mitgeschickt, nicht in die Stufe eingerechnet
            notifier.send_signal_notification(signal, relevant_news)
            state_module.mark_notified(persisted_state, signal)
            sent_count += 1
            time.sleep(1)  # ntfy.sh nicht überlasten

    state_module.save_state(persisted_state)
    print(f"Fertig. {sent_count} Benachrichtigungen gesendet.")


if __name__ == "__main__":
    run()
