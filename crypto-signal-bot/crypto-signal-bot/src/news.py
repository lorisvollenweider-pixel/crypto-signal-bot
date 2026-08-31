"""
Holt aktuelle Krypto-News über kostenlose RSS-Feeds und bewertet sie
per einfachem Keyword-Scan als positiv/negativ.

WICHTIG: Das ist eine simple Heuristik, kein echtes Sprachverständnis.
Für bessere Sentiment-Analyse könnte man hier später die Anthropic API
einbauen (kostet dann aber pro Anfrage).
"""

import time
from datetime import datetime, timedelta, timezone

import feedparser

from src import config


def fetch_recent_news() -> list[dict]:
    """Lädt aktuelle Artikel aus allen konfigurierten RSS-Feeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.NEWS_LOOKBACK_HOURS)
    articles = []

    for feed_url in config.RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue

        for entry in feed.entries:
            published = _parse_date(entry)
            if published and published < cutoff:
                continue
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            articles.append({
                "title": title,
                "summary": summary,
                "link": entry.get("link", ""),
                "published": published,
                "source": feed.feed.get("title", feed_url),
            })
    return articles


def _parse_date(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        val = entry.get(field)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc)
    return None


def score_sentiment(text: str) -> int:
    """Simpler Keyword-Score: +1 pro positivem, -1 pro negativem Treffer."""
    text_lower = text.lower()
    score = 0
    for kw in config.POSITIVE_KEYWORDS:
        if kw in text_lower:
            score += 1
    for kw in config.NEGATIVE_KEYWORDS:
        if kw in text_lower:
            score -= 1
    return score


def match_coins_in_news(articles: list[dict], watchlist: list[dict]) -> dict[str, list[dict]]:
    """
    Ordnet News-Artikel den Coins aus der Watchlist zu (per Namens-/Symbol-Suche)
    und gibt pro Coin-Symbol eine Liste relevanter, bewerteter Artikel zurück.
    """
    coin_news = {}
    for coin in watchlist:
        symbol = coin["symbol"]
        name = coin["name"].lower()
        relevant = []
        for article in articles:
            haystack = f"{article['title']} {article['summary']}".lower()
            if name in haystack or f" {symbol.lower()} " in f" {haystack} ":
                sentiment = score_sentiment(haystack)
                if sentiment != 0:
                    relevant.append({**article, "sentiment": sentiment})
        if relevant:
            coin_news[symbol] = relevant
    return coin_news
