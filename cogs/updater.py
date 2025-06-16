import os
import json
import asyncio
import logging
from datetime import datetime
from discord import Embed
from discord.ext import commands, tasks
import aiohttp

# Konfiguration
INTERVAL      = int(os.getenv("UPDATE_INTERVAL", "60"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY",  "1.0"))
CONFIG_PATH   = "config.json"

logger = logging.getLogger(__name__)

def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.error(f"Kann {CONFIG_PATH} nicht laden: {e}")
        return {}

def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logger.error(f"Kann {CONFIG_PATH} nicht speichern: {e}")

class Updater(commands.Cog):
    """Cog für Preis-Embeds: rein TradingView-Batch, persistent message_id, moderner Embed."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.msg = None
        self.last_channel_id = None
        self.update_loop.start()

    def cog_unload(self):
        self.update_loop.cancel()

    async def _fetch_batch(self, session: aiohttp.ClientSession, screener: str, tickers: list[str]):
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {"symbols": {"tickers": tickers}, "columns": ["open", "close"]}
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            js = await resp.json()
            return js.get("data", [])

    @tasks.loop(seconds=INTERVAL)
    async def update_loop(self):
        if not self.bot.is_ready():
            return

        cfg = load_config()
        channel_id = cfg.get("embed_channel")
        if not channel_id:
            return

        # 1) Alte Nachricht bei Neustart wiederherstellen
        if self.msg is None and cfg.get("message_id"):
            ch = self.bot.get_channel(channel_id)
            if ch:
                try:
                    self.msg = await ch.fetch_message(cfg["message_id"])
                except Exception:
                    self.msg = None

        # 2) Kanalwechsel: altes Embed nur beim echten Switch löschen
        if self.last_channel_id is not None and channel_id != self.last_channel_id:
            if self.msg:
                try: await self.msg.delete()
                except: pass
                self.msg = None
        self.last_channel_id = channel_id

        # 3) Kanal holen
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            logger.warning(f"Kanal-ID {channel_id} nicht gefunden.")
            return

        # 4) Assets aus Config
        stock_cfgs  = cfg.get("stocks", [])
        crypto_cfgs = cfg.get("cryptos", [])

        # Gruppieren für Batch-API
        stock_groups = {}
        for s in stock_cfgs:
            scr = s.get("screener", "america")
            ticker = f"{s['exchange'].upper()}:{s['symbol'].upper()}"
            stock_groups.setdefault(scr, []).append(ticker)

        crypto_groups = {}
        for c in crypto_cfgs:
            scr = c.get("screener", "crypto")
            ticker = f"{c['exchange'].upper()}:{c['symbol'].upper()}"
            crypto_groups.setdefault(scr, []).append(ticker)

        stock_map = {}
        crypto_map = {}
        headers   = {"User-Agent": "Mozilla/5.0"}

        # 5) Batch-Anfragen
        async with aiohttp.ClientSession(headers=headers) as session:
            for scr, tickers in stock_groups.items():
                await asyncio.sleep(REQUEST_DELAY)
                try:
                    data = await self._fetch_batch(session, scr, tickers)
                    for item in data:
                        stock_map[item["s"]] = item["d"]
                except Exception as e:
                    logger.error(f"Stock-Batch({scr})-Fehler: {e}")

            for scr, tickers in crypto_groups.items():
                await asyncio.sleep(REQUEST_DELAY)
                try:
                    data = await self._fetch_batch(session, scr, tickers)
                    for item in data:
                        crypto_map[item["s"]] = item["d"]
                except Exception as e:
                    logger.error(f"Crypto-Batch({scr})-Fehler: {e}")

        # 6) Moderner Embed bauen
        color = 0x1abc9c  # frisches Grün-Blau
        embed = Embed(
            title="📊 Cryptic Tracker",
            description=f"↻ Aktualisierung alle {INTERVAL}s",
            color=color,
            timestamp=datetime.utcnow()
        )
        # Autor mit Bot-Avatar
        embed.set_author(
            name="Cryptic",
            icon_url=self.bot.user.display_avatar.url
        )
        # Stocks-Liste
        stock_lines = []
        for s in stock_cfgs:
            key = f"{s['exchange'].upper()}:{s['symbol'].upper()}"
            o, c = stock_map.get(key, (None, None))
            if o is not None:
                pct = (c - o) / o * 100 if o else 0
                arrow = "🔼" if pct >= 0 else "🔻"
                stock_lines.append(f"`{s['symbol'].upper()}` {arrow} **${c:.2f}** ({pct:+.2f}%)")
            else:
                stock_lines.append(f"`{s['symbol'].upper()}` ❌ Keine Daten")
        embed.add_field(
            name="📈 Aktien",
            value="\n".join(stock_lines) or "—",
            inline=False
        )
        # Crypto-Liste
        crypto_lines = []
        for c in crypto_cfgs:
            key = f"{c['exchange'].upper()}:{c['symbol'].upper()}"
            o, p = crypto_map.get(key, (None, None))
            if o is not None:
                pct = (p - o) / o * 100 if o else 0
                arrow = "🔼" if pct >= 0 else "🔻"
                crypto_lines.append(f"`{c['symbol'].upper()}` {arrow} **${p:.4f}** ({pct:+.2f}%)")
            else:
                crypto_lines.append(f"`{c['symbol'].upper()}` ❌ Keine Daten")
        embed.add_field(
            name="🔗 Kryptowährungen",
            value="\n".join(crypto_lines) or "—",
            inline=False
        )
        # Footer
        embed.set_footer(text="Powered by TradingView")

        # 7) Senden oder Editieren
        try:
            if self.msg is None:
                sent = await channel.send(embed=embed)
                self.msg = sent
                cfg["message_id"] = sent.id
                save_config(cfg)
            else:
                await self.msg.edit(embed=embed)
        except Exception as e:
            logger.error(f"Fehler beim Senden/Editieren des Embeds: {e}")

    @update_loop.before_loop
    async def before(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Updater(bot))
