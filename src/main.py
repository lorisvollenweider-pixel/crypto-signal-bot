"""
Hauptskript: Wird von der GitHub Action alle 5 Minuten ausgeführt.

Ablauf:
1. Top-Coins + Kursdaten laden
2. Technische Signale berechnen
3. Relevante News laden und Coins zuordnen
4. Cooldown/Dedup prüfen, Signale in Historie speichern
5. Benachrichtigungen über ntfy.sh senden (nur ab Stufe NOTIFY_MIN_TIER)
6. Ältere Signale automatisch auswerten (richtig/falsch gelegen?)
7. Zustand speichern
"""

import sys
import time

from src import config, data_fetcher, indicators, news, notifier, state as state_module, history as history_module


def run():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starte Scan...")

    print("Lade Watchlist (Top Coins)...")
    watchlist = data_fetcher.build_watchlist()
    print(f"{len(watchlist)} Coins in Watchlist (mit KuCoin-Handelspaar).")

    if not watchlist:
        print("FEHLER: Keine Watchlist geladen, breche ab.")
        sys.exit(1)

    # Nachschlage-Hilfe: Symbol -> KuCoin-Handelspaar (für die Historie)
    kucoin_symbol_by_coin = {c["symbol"]: c["kucoin_symbol"] for c in watchlist}

    print("Lade Kursdaten...")
    klines = data_fetcher.fetch_all_klines(watchlist)
    print(f"Kursdaten für {len(klines)} Coins geladen.")

    print("Berechne technische Signale...")
    signals = indicators.analyze_all(klines)
    print(f"{len(signals)} Signale gefunden (alle Stufen).")

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
    signal_history = history_module.load_history()
    sent_count = 0

    for signal in signals:
        # Jedes Signal wird in der Historie festgehalten (für die spätere
        # Erfolgs-Auswertung), aber nur ab NOTIFY_MIN_TIER auch gepusht.
        if state_module.should_notify(persisted_state, signal):
            kucoin_symbol = kucoin_symbol_by_coin.get(signal["symbol"])
            if kucoin_symbol:
                history_module.record_signal(signal_history, signal, kucoin_symbol)

            if signal["tier"] >= config.NOTIFY_MIN_TIER:
                relevant_news = coin_news.get(signal["symbol"])
                notifier.send_signal_notification(signal, relevant_news)
                sent_count += 1
                time.sleep(1)  # ntfy.sh nicht überlasten

            state_module.mark_notified(persisted_state, signal)

    state_module.save_state(persisted_state)
    print(f"Fertig. {sent_count} Benachrichtigungen gesendet (Stufe {config.NOTIFY_MIN_TIER}+).")

    # --- Erfolgs-Auswertung älterer Signale ---
    print("Werte fällige ältere Signale aus...")
    newly_evaluated = history_module.evaluate_due_signals(signal_history)
    if newly_evaluated:
        print(f"{len(newly_evaluated)} Signale ausgewertet, sende Zusammenfassung...")
        notifier.send_outcome_summary(newly_evaluated)
    else:
        print("Keine fälligen Signale zur Auswertung.")

    signal_history = history_module.prune_old_history(signal_history)
    history_module.save_history(signal_history)


if __name__ == "__main__":
    run()
