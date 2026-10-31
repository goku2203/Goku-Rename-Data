
import aiohttp, asyncio, warnings, pytz, datetime, os
import logging
import logging.config
import glob, sys
import importlib.util
from pathlib import Path

# pyrogram imports
from pyrogram import Client, __version__, errors
from pyrogram.raw.all import layer
from pyrogram import idle

# bots imports
from config import Config
from helper.database import goku_stark
from plugins.web_support import web_server
from plugins.file_rename import app

# Get logging configurations
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler('BotLog.txt'),
             logging.StreamHandler()]
)
logging.getLogger("pyrofork").setLevel(logging.WARNING)


# ---------------- KEEP ALIVE + RENDER HOURS ALERT ----------------
# RENDER_HOURS_ALERT  : intha hours-ku mela pona LOG_CHANNEL + admin-ku alert (default 700)
# RENDER_HOURS_LIMIT  : Render free limit (default 750)
# RENDER_OTHER_SERVICES : same Render account-la 24/7 odura vera free service count (default 0)
#                         (750 hours ellaa free service-kum serthu thaan, adhunaala adhaiyum count pannanum)
PING_EVERY = 240  # seconds

async def _send_hours_alert(used_hours, alert_at, limit):
    left = max(limit - used_hours, 0)
    text = (
        "**\u26a0\ufe0f Render Free Hours Alert**\n\n"
        f"Intha month use aana hours: **{used_hours:.1f} / {limit:.0f}**\n"
        f"Meedham iruppadhu: **{left:.1f} hrs** (approx)\n\n"
        "Limit mudinja Render ella free service-um suspend pannidum. "
        "Munnadiye vera Render account-la deploy panna ready aagu, illa paid plan-ku maaru.\n\n"
        "__Note: ithu bot-oda own counter (approx). Exact value Render dashboard > Billing-la paaru.__"
    )
    targets = [Config.LOG_CHANNEL] + [a for a in Config.ADMIN if isinstance(a, int)]
    for chat in targets:
        try:
            await Config.BOT.send_message(chat, text)
        except Exception as e:
            logging.error(f"Hours alert send failed for {chat}: {e}")

async def _track_hours():
    """Ovvoru ping-kum 240s add pannum, threshold thaandina oru thadava alert anuppum."""
    alert_at = float(os.environ.get("RENDER_HOURS_ALERT", "700"))
    limit = float(os.environ.get("RENDER_HOURS_LIMIT", "750"))
    others = int(os.environ.get("RENDER_OTHER_SERVICES", "0"))
    month = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    meta = goku_stark.db.meta

    doc = await meta.find_one_and_update(
        {"_id": "render_hours", "month": month},
        {"$inc": {"seconds": PING_EVERY * (1 + others)}},
        return_document=True,
    )
    if doc is None:  # puthu month (illa first time) -> reset
        await meta.replace_one(
            {"_id": "render_hours"},
            {"_id": "render_hours", "month": month,
             "seconds": PING_EVERY * (1 + others), "alerted": False},
            upsert=True,
        )
        doc = await meta.find_one({"_id": "render_hours"})

    used_hours = doc["seconds"] / 3600
    if used_hours >= alert_at and not doc.get("alerted"):
        await _send_hours_alert(used_hours, alert_at, limit)
        await meta.update_one({"_id": "render_hours"}, {"$set": {"alerted": True}})

async def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        return
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url + "/health", timeout=aiohttp.ClientTimeout(total=20)) as r:
                    await r.read()
            except Exception as e:
                logging.error(f"Keep-alive failed: {e}")
            try:
                await _track_hours()
            except Exception as e:
                logging.error(f"Hours tracking failed: {e}")
            await asyncio.sleep(PING_EVERY)

class DigitalAutoRenameBot(Client):
    def __init__(self):
        super().__init__(
            name="DigitalRenameBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=5,
            max_concurrent_transmissions=10
        )
                
         
    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username  
        self.uptime = Config.BOT_UPTIME
        self.premium = Config.PREMIUM_MODE
        self.uploadlimit = Config.UPLOAD_LIMIT_MODE
        Config.BOT = self
        
        # Web server for Render binding
        app = aiohttp.web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await aiohttp.web.TCPSite(app, bind_address, Config.PORT).start()
        self.keep_alive_task = asyncio.create_task(keep_alive())
        
        path = "plugins/*.py"
        files = glob.glob(path)
        for name in files:
            with open(name) as a:
                patt = Path(a.name)
                plugin_name = patt.stem.replace(".py", "")
                plugins_path = Path(f"plugins/{plugin_name}.py")
                import_path = "plugins.{}".format(plugin_name)
                spec = importlib.util.spec_from_file_location(import_path, plugins_path)
                load = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(load)
                sys.modules["plugins" + plugin_name] = load
                print("Digital Botz Imported " + plugin_name)
                
        print(f"{me.first_name} Iꜱ Sᴛᴀʀᴛᴇᴅ.....✨️")

        # Admin kku only "Bot Online" msg mattum anuppum
        for id in Config.ADMIN:
            try: 
                await self.send_message(id, f"**Bot Online ⚡**")                                
            except: 
                pass
                    
        # Log channel message sending removed as requested.

    async def stop(self, *args):
        # Bot stopped msg ah admin kku anuppuratha remove panniyachu
        print("Bot Stopped 🙄")
        await super().stop()


digital_instance = DigitalAutoRenameBot()

def main():
    async def start_services():
        if Config.STRING_SESSION:
            await asyncio.gather(app.start(), digital_instance.start())
        else:
            await asyncio.gather(digital_instance.start())
        
        # Idle mode start karo
        await idle()
        
        # Bot stop karo
        if Config.STRING_SESSION:
            await asyncio.gather(app.stop(), digital_instance.stop())
        else:
            await asyncio.gather(digital_instance.stop())

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user!")
    finally:
        loop.close()

if __name__ == "__main__":
    warnings.filterwarnings("ignore", message="There is no current event loop")
    try:
        main()
    except errors.FloodWait as ft:
        print(f"⏳ FloodWait: Sleeping for {ft.value} seconds")
        asyncio.run(asyncio.sleep(ft.value))
        print("Now Ready For Deploying!")
        main()
