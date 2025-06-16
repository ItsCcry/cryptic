import os
import json
import discord
import aiohttp
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View

# ---------- Env & Config ----------
load_dotenv()
TOKEN           = os.getenv("DISCORD_TOKEN")
APP_ID          = int(os.getenv("APPLICATION_ID",  "0"))
GUILD_ID        = int(os.getenv("GUILD_ID",        "0")) if os.getenv("GUILD_ID") else None
PREFIX          = os.getenv("BOT_PREFIX",         "!")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "60"))
CONFIG_PATH     = "config.json"

def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

# ---------- Screener-Helper ----------
US_EXCHANGES   = {"NASDAQ", "NYSE", "AMEX", "BATS", "OTC"}
EU_EXCHANGES   = {"XETRA", "TRADEGATE", "FWB", "LSE", "EURONEXT", "BME"}
ASIA_EXCHANGES = {"TSE", "HKEX", "SSE", "SZSE"}

def get_stock_screener(exchange: str) -> str:
    e = exchange.upper()
    if e in US_EXCHANGES:   return "america"
    if e in EU_EXCHANGES:   return "europe"
    if e in ASIA_EXCHANGES: return "asia"
    return "america"

def get_crypto_screener(exchange: str) -> str:
    e = exchange.upper()
    if "FOREX" in e:        return "forex"
    return "crypto"

# ---------- Asset-Select UI ----------
class AssetSelect(Select):
    def __init__(self, options: list[discord.SelectOption], asset_type: str):
        super().__init__(
            placeholder="Wähle dein Asset aus…",
            min_values=1, max_values=1,
            options=options
        )
        self.asset_type = asset_type  # "stock" oder "crypto"

    async def callback(self, interaction: discord.Interaction):
        sym, exch = self.values[0].split(":", 1)
        cfg = load_config()

        # Screener automatisch ermitteln
        if self.asset_type == "stock":
            scr = get_stock_screener(exch)
            key = "stocks"
        else:
            scr = get_crypto_screener(exch)
            key = "cryptos"

        entry = {"symbol": sym, "exchange": exch, "screener": scr}
        existing = [e for e in cfg.setdefault(key, []) if e["symbol"] == sym and e["exchange"] == exch]
        if existing:
            content = f"❗ `{sym}` auf `{exch}` ist bereits in der Liste."
        else:
            cfg[key].append(entry)
            save_config(cfg)
            content = (
                f"✅ `{sym}` auf `{exch}` hinzugefügt.\n"
                f"Screener: `{scr}` – erscheint beim nächsten Update."
            )

        await interaction.response.edit_message(content=content, embed=None, view=None)

# ---------- Delete-Select UI ----------
class DeleteSelect(Select):
    def __init__(self, options: list[discord.SelectOption], asset_type: str):
        super().__init__(
            placeholder="Wähle ein Asset zum Entfernen…",
            min_values=1, max_values=1,
            options=options
        )
        self.asset_type = asset_type  # "stock" oder "crypto"

    async def callback(self, interaction: discord.Interaction):
        sym, exch = self.values[0].split(":", 1)
        cfg = load_config()
        key = "stocks" if self.asset_type == "stock" else "cryptos"
        entries = cfg.get(key, [])
        cfg[key] = [e for e in entries if not (e["symbol"] == sym and e["exchange"] == exch)]
        save_config(cfg)
        content = f"🗑️ `{sym}` auf `{exch}` entfernt.\nEs verschwindet beim nächsten Update."
        await interaction.response.edit_message(content=content, embed=None, view=None)

# ---------- Bot Setup ----------
class CrypticBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=PREFIX, intents=intents, application_id=APP_ID)

    async def setup_hook(self):
        # Cogs (Updater, etc.)
        for fn in os.listdir("cogs"):
            if fn.endswith(".py") and fn != "__init__.py":
                await self.load_extension(f"cogs.{fn[:-3]}")
        # Slash-Command Sync
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"✅ Commands synced to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print("✅ Commands globally synced")

    async def on_ready(self):
        print(f"🔌 Eingeloggt als {self.user}")

bot = CrypticBot()

# ---------- /add_asset ----------
@bot.tree.command(
    name="add_asset",
    description="Fügt eine Aktie oder Kryptowährung hinzu (Live-Suche)"
)
@app_commands.describe(
    asset_type="Aktie oder Krypto?",
    query="Suchbegriff, z.B. 'Apple' oder 'Bitcoin'"
)
@app_commands.choices(asset_type=[
    app_commands.Choice(name="Aktie", value="stock"),
    app_commands.Choice(name="Krypto", value="crypto"),
])
async def add_asset(
    interaction: discord.Interaction,
    asset_type: app_commands.Choice[str],
    query: str
):
    await interaction.response.defer(ephemeral=True)
    type_key = asset_type.value

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }
    params = {"text": query, "exchange": "", "type": type_key, "limit": 25}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(
            "https://symbol-search.tradingview.com/symbol_search/",
            params=params
        ) as resp:
            if resp.status != 200:
                return await interaction.followup.send(
                    f"⚠️ Suche fehlgeschlagen (HTTP {resp.status}).",
                    ephemeral=True
                )
            ct = resp.headers.get("Content-Type", "")
            if "application/json" not in ct:
                text = await resp.text()
                return await interaction.followup.send(
                    f"⚠️ Unerwarteter Content-Type: {ct}\n{text[:200]}…",
                    ephemeral=True
                )
            data = await resp.json()

    seen = set()
    options = []
    for item in data:
        sym = item["symbol"]
        exch = item["exchange"]
        val = f"{sym}:{exch}"
        if val in seen:
            continue
        seen.add(val)
        options.append(discord.SelectOption(
            label=f"{sym} ({exch})",
            value=val
        ))
        if len(options) >= 25:
            break

    if not options:
        return await interaction.followup.send(
            f"🔍 Keine Treffer für `{query}` gefunden.",
            ephemeral=True
        )

    view = View(timeout=60)
    view.add_item(AssetSelect(options=options, asset_type=type_key))
    await interaction.followup.send(
        f"🔍 Ergebnisse für **{query}** ({asset_type.name}):",
        view=view,
        ephemeral=True
    )

# ---------- /delete_asset ----------
@bot.tree.command(
    name="delete_asset",
    description="Entfernt eine Aktie oder Kryptowährung via Dropdown"
)
@app_commands.describe(
    asset_type="Typ wählen"
)
@app_commands.choices(asset_type=[
    app_commands.Choice(name="Aktie", value="stock"),
    app_commands.Choice(name="Krypto", value="crypto"),
])
async def delete_asset(
    interaction: discord.Interaction,
    asset_type: app_commands.Choice[str]
):
    await interaction.response.defer(ephemeral=True)
    key = "stocks" if asset_type.value == "stock" else "cryptos"
    cfg = load_config()
    entries = cfg.get(key, [])
    if not entries:
        return await interaction.followup.send(
            f"❗ Keine {asset_type.name}-Einträge in der Liste.",
            ephemeral=True
        )

    options = []
    for e in entries:
        label = f"{e['symbol']} ({e['exchange']})"
        val   = f"{e['symbol']}:{e['exchange']}"
        options.append(discord.SelectOption(label=label, value=val))
        if len(options) >= 25:
            break

    view = View(timeout=60)
    view.add_item(DeleteSelect(options=options, asset_type=asset_type.value))
    await interaction.followup.send(
        f"🗑️ Wähle eine {asset_type.name} zum Entfernen:",
        view=view,
        ephemeral=True
    )

bot.run(TOKEN)
