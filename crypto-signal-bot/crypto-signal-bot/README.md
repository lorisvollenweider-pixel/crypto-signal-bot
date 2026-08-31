# Crypto Signal Bot

Beobachtet automatisch die Top ~150 Kryptowährungen, erkennt technische
Signale (RSI, MACD, Bollinger Bands, EMA-Trends, Volumen-Spikes) und
kombiniert sie mit aktuellen Krypto-News. Schickt dir bei relevanten
Treffern eine Push-Benachrichtigung aufs Handy – komplett kostenlos,
läuft automatisch alle 15 Minuten über GitHub Actions.

## ⚠️ Wichtiger Disclaimer

Dieses Tool ist **kein Finanzberater und keine Kaufempfehlung**. Es zeigt
dir statistische Auffälligkeiten in Kursdaten und News – keine
Vorhersagen. Krypto-Preise sind extrem volatil und unvorhersehbar.
Nutze die Signale nur als **einen von mehreren Anhaltspunkten** für
deine eigene Recherche, niemals als alleinige Entscheidungsgrundlage.
Investiere nie mehr, als du bereit bist zu verlieren.

## Wie die Stufen (Tiers) zu verstehen sind

- **Stufe 1** – Ein erstes, schwaches Signal. Nur beobachten, nicht handeln.
- **Stufe 2** – Mehrere Indikatoren stimmen überein. Erhöhte Wahrscheinlichkeit,
  aber immer noch keine Garantie.
- **Stufe 3** – Die Bewegung hat bereits sichtbar eingesetzt (Preis + Volumen
  bestätigen einen laufenden Trend).

## Einrichtung (einmalig, ca. 15 Minuten)

### 1. ntfy.sh App installieren
- Lade die **ntfy** App runter: [iOS](https://apps.apple.com/app/ntfy/id1625396347) /
  [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- Öffne die App → "+" → gib ein **eigenes, einzigartiges Topic** ein,
  z.B. `dein-name-crypto-alerts-xk29` (möglichst ungewöhnlich, da jeder,
  der den Topic-Namen kennt, deine Nachrichten mitlesen kann – es ist
  kein privater Account, sondern ein öffentlicher aber unauffindbarer Kanal)
- Merk dir diesen Namen, den brauchst du gleich

### 2. GitHub Repository erstellen
1. Gehe auf [github.com](https://github.com) → Account erstellen (falls noch nicht vorhanden, kostenlos)
2. Neues Repository erstellen, z.B. `crypto-signal-bot` → **Public** auswählen
   (wichtig: bei **öffentlichen** Repos sind GitHub Actions Minuten
   unbegrenzt kostenlos, bei privaten nur 2.000 Min/Monat – bei einem
   Lauf alle 15 Min würde das bei einem privaten Repo nicht reichen.
   Dein `NTFY_TOPIC` bleibt trotzdem geheim, der liegt als **Secret**,
   nicht im Code. Es landet also nichts Sensibles öffentlich sichtbar)
3. Lade alle Dateien aus diesem Projekt in das Repository hoch
   (einfachster Weg: über die GitHub-Weboberfläche "Add file" → "Upload files",
   oder falls du Claude Code nutzt, kannst du es damit direkt pushen)

### 3. Secret für dein ntfy-Topic hinterlegen
1. Im Repository: **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Name: `NTFY_TOPIC`
4. Wert: dein Topic-Name aus Schritt 1 (z.B. `dein-name-crypto-alerts-xk29`)
5. Speichern

### 4. Workflow aktivieren
1. Gehe im Repository auf den Tab **Actions**
2. Falls gefragt, Workflows aktivieren (bei privaten Repos manchmal nötig)
3. Wähle **Crypto Signal Scan** aus der Liste
4. Klicke **Run workflow** für einen ersten manuellen Test-Lauf
5. Nach ca. 1-2 Minuten solltest du (falls ein Signal gefunden wurde) eine
   Benachrichtigung auf dem Handy bekommen

Ab jetzt läuft es automatisch alle 15 Minuten – auch wenn dein Laptop
aus ist, dein Handy im Flugmodus war, völlig egal. GitHub Actions
kümmert sich darum.

## Einstellungen anpassen

Alle wichtigen Werte kannst du in `src/config.py` ändern, ohne die
restliche Logik zu verstehen:

- `TOP_N_COINS` – wie viele Coins beobachtet werden
- `TIMEFRAME` – welches Kerzenintervall (z.B. `1h`, `4h`, `1d`)
- `RSI_OVERSOLD` / `RSI_OVERBOUGHT` – RSI-Schwellwerte
- `VOLUME_SPIKE_FACTOR` – ab welchem Vielfachen des Durchschnitts ein
  Volumen-Ausschlag zählt
- `COOLDOWN_HOURS` – wie lange ein Coin nach einer Meldung "still" bleibt,
  bevor er auf derselben Stufe erneut melden darf (verhindert Spam)
- `POSITIVE_KEYWORDS` / `NEGATIVE_KEYWORDS` – Wörter für die News-Bewertung

Nach Änderungen einfach committen/pushen – der nächste automatische
Lauf nutzt die neuen Werte.

## Projektstruktur

```
src/
  config.py       Einstellungen
  data_fetcher.py Coin-Liste (CoinGecko) + Kursdaten (Binance)
  indicators.py   Technische Analyse & Signal-/Stufen-Logik
  news.py         RSS-News laden & bewerten
  notifier.py     ntfy.sh Benachrichtigungen
  state.py        Verhindert doppelte Meldungen (Cooldown)
  main.py         Führt alles zusammen aus
data/
  state.json      Gespeicherter Zustand (wird automatisch aktualisiert)
.github/workflows/
  scan.yml        GitHub Actions Zeitplan (alle 15 Min)
```

## Geplante Erweiterungen (Phase 2)

- Aktien-Kurse & Firmen-News dazu
- Mehr Coins / weitere Timeframes gleichzeitig
- Bessere News-Sentiment-Analyse per Anthropic API statt Keyword-Scan
- Eigenes Dashboard (Web-Ansicht) statt nur Push-Nachrichten

## Kosten

Bei normaler Nutzung: **0€/Monat.**
- CoinGecko & Binance API: kostenlos
- GitHub Actions: **unbegrenzt kostenlos bei öffentlichem Repository**
  (bei privatem Repo nur 2.000 Min/Monat, reicht bei alle 15 Min nicht aus –
  siehe Hinweis oben, deswegen Public-Repo verwenden)
- ntfy.sh: kostenlos
