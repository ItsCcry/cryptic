# Cryptic

**Cryptic** ist ein erweiterbarer Discord-Bot für Live-Preistracking von Aktien & Kryptowährungen – ausschließlich über **TradingView**.

## Features

- **Autocomplete-Suche** für Aktien & Krypto (TradingView-Symbol-Search API)  
- **Slash-Commands**  
  - `/add_asset` – Aktie oder Krypto suchen & hinzufügen  
  - `/delete_asset` – Aktie oder Krypto entfernen  
  - `/set_channel` – Kanal für Embed-Updates setzen  
- **Embed** mit aktuellem Preis & %-Änderung  
- **Automatisches Editieren** des Embeds im eingestellten Intervall (`UPDATE_INTERVAL`)  
- **Persistent Message ID**: Embed wird auch nach Neustart nur editiert, nicht neu gesendet  
- **Vollständig konfigurierbar** per `config.json` oder Slash-Commands  
- **Erweiterbar** durch eigene Cogs

## Environment / `.env`

Kopiere die Beispiel-Datei und fülle deine Werte ein:

```bash
cp .env.example .env
```

```dotenv
DISCORD_TOKEN=dein_discord_bot_token  
APPLICATION_ID=deine_application_id  
GUILD_ID=deine_guild_id          # Optional: nur für schnelle Guild-Registrierung  
BOT_PREFIX=!                     # Nur falls du Legacy-Commands nutzen willst  
UPDATE_INTERVAL=5                # Sek. zwischen Embed-Updates  
REQUEST_DELAY=1.0                # Sek. Pause zwischen einzelnen Batch-Anfragen  
```

## Beispiel `config.json`

Kopiere auch hier die Beispiel-Datei:

```bash
cp config.json.example config.json
```

```json
{
  "stocks": [
    { "symbol": "AAPL",   "exchange": "NASDAQ", "screener": "america" },
    { "symbol": "MSFT",   "exchange": "NASDAQ", "screener": "america" }
  ],
  "cryptos": [
    { "symbol": "BTCUSDT", "exchange": "BINANCE", "screener": "crypto" },
    { "symbol": "RAIRUSD", "exchange": "CRYPTO",  "screener": "crypto" }
  ],
  "embed_channel": 123456789012345678,
  "message_id":    null
}
```

## Installation

```bash
git clone https://github.com/DeinUser/cryptic.git
cd cryptic
python3 -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate      # Windows
pip install -r requirements.txt
# .env und config.json wie oben anlegen
python bot.py
```

## Usage

1. `/set_channel #preis-tracker`  
2. `/add_asset` – wähle „Aktie“ oder „Krypto“, gib Namen ein, Dropdown auswählen  
3. `/delete_asset` – wähle Typ, Dropdown mit vorhandenen Assets zum Entfernen  
4. Embed erscheint im Kanal und **editiert** sich alle `UPDATE_INTERVAL` Sek.

