from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import requests
import asyncio
import warnings
import os

# === CONFIGURATION ===
BOT_TOKEN = "8028470688:AAH1DZ4BdlMjQTlloFjm2BWilsWw4ZtP05I"
chat_id_path = "chat_id.txt"
CHAT_ID = None
notified_today = False

# === LOAD CHAT ID IF SAVED ===
if os.path.exists(chat_id_path):
    try:
        with open(chat_id_path) as f:
            CHAT_ID = int(f.read().strip())
    except Exception:
        CHAT_ID = None

warnings.filterwarnings("ignore", category=DeprecationWarning)

bot = Bot(token=BOT_TOKEN)
app = ApplicationBuilder().token(BOT_TOKEN).build()
loop = asyncio.get_event_loop_policy().get_event_loop()

# === FETCH 12PM BTC PRICE ===
def fetch_btc_price():
    now_sgt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    noon_sgt = now_sgt.replace(hour=12, minute=0, second=0, microsecond=0)
    noon_utc = noon_sgt.astimezone(datetime.timezone.utc)

    end_time = int(noon_utc.timestamp() * 1000)
    start_time = end_time - 60_000

    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_time}&endTime={end_time}&limit=1"
    resp = requests.get(url)

    if resp.status_code == 200 and resp.json():
        close_price = float(resp.json()[0][4])
        if CHAT_ID:
            asyncio.run_coroutine_threadsafe(
                bot.send_message(chat_id=CHAT_ID, text=f"📈 BTC/USDT close at 12:00 PM SGT: ${close_price:,.2f}"),
                loop
            )
    elif CHAT_ID:
        asyncio.run_coroutine_threadsafe(
            bot.send_message(chat_id=CHAT_ID, text="⚠️ Failed to fetch BTC/USDT 12PM price."),
            loop
        )

# === ALERT IF CURRENT PRICE EXCEEDS TARGET ===
def alert_if_above_target():
    global notified_today
    try:
        now_sgt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        today = now_sgt.date()

        sgt_midnight = datetime.datetime.combine(today, datetime.time(0, 0), tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        utc_midnight = sgt_midnight.astimezone(datetime.timezone.utc)
        end_time = int((utc_midnight + datetime.timedelta(minutes=1)).timestamp() * 1000)
        start_time = end_time - 60_000

        resp = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_time}&endTime={end_time}&limit=1")
        if resp.status_code != 200 or not resp.json():
            return

        close_price = float(resp.json()[0][4])
        target_price = close_price * 1.02

        now_resp = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
        if now_resp.status_code != 200:
            return

        current_price = float(now_resp.json()['price'])

        print(f"[Check] Now: {current_price:.2f} | Target: {target_price:.2f} | Notified: {notified_today}")

        if current_price >= target_price and not notified_today and CHAT_ID:
            asyncio.run_coroutine_threadsafe(
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=(
                        f"🚨 *BTC has hit your +2% target!*\n\n"
                        f"🎯 *Target:* ${target_price:,.2f}\n"
                        f"📈 *Now:* ${current_price:,.2f}"
                    ),
                ),
                loop
            )
            notified_today = True

        # Reset flag shortly after midnight
        if now_sgt.hour == 0 and now_sgt.minute < 5:
            notified_today = False

    except Exception as e:
        print("Alert error:", str(e))

# === COMMAND HANDLERS ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    with open(chat_id_path, "w") as f:
        f.write(str(CHAT_ID))
    await update.message.reply_text(
        "Welcome! You’ve been registered for BTC alerts.\n"
        "✅ You'll receive:\n"
        "- Daily 12PM BTC/USDT price\n"
        "- Alerts when price exceeds +2% from 00:00 close."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    with open(chat_id_path, "w") as f:
        f.write(str(CHAT_ID))

    msg = update.message.text.lower()
    if msg == "hi":
        await update.message.reply_text("goliath online!")
    else:
        await update.message.reply_text("Say 'hi' to check if I'm alive.")

async def btcnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    resp = requests.get(url)
    if resp.status_code == 200:
        price = float(resp.json()['price'])
        await update.message.reply_text(f"💰 BTC/USDT now: ${price:,.2f}")
    else:
        await update.message.reply_text("❌ Failed to fetch BTC price.")

async def btc12am(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❗Usage: /btc12am YYYY-MM-DD")
        return
    try:
        date_str = context.args[0]
        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        sgt_midnight = datetime.datetime.combine(target_date, datetime.time(0, 0), tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        utc_midnight = sgt_midnight.astimezone(datetime.timezone.utc)
        end_time = int((utc_midnight + datetime.timedelta(minutes=1)).timestamp() * 1000)
        start_time = end_time - 60_000

        resp = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_time}&endTime={end_time}&limit=1")
        if resp.status_code == 200 and resp.json():
            close_price = float(resp.json()[0][4])
            plus_2 = close_price * 1.02
            await update.message.reply_text(
                f"🕛 BTC/USDT close at 00:00 AM SGT on {date_str}: ${close_price:,.2f}\n"
                f"🔼 +2% target: ${plus_2:,.2f}"
            )
        else:
            await update.message.reply_text("⚠️ No data found.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def btcday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        now_sgt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        today = now_sgt.date()
        sgt_midnight = datetime.datetime.combine(today, datetime.time(0, 0), tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        utc_midnight = sgt_midnight.astimezone(datetime.timezone.utc)
        end_time = int((utc_midnight + datetime.timedelta(minutes=1)).timestamp() * 1000)
        start_time = end_time - 60_000

        resp = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_time}&endTime={end_time}&limit=1")
        if resp.status_code != 200 or not resp.json():
            await update.message.reply_text("⚠️ No 00:00 SGT candle found for today.")
            return
        close_price = float(resp.json()[0][4])
        plus_2 = close_price * 1.02

        await update.message.reply_text(
            f"📆 /btcday ({today})\n"
            f"🕛 00:00 AM SGT close: ${close_price:,.2f}\n"
            f"🔼 +2% target: ${plus_2:,.2f}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# === BIND HANDLERS ===
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("btcnow", btcnow))
app.add_handler(CommandHandler("btc12am", btc12am))
app.add_handler(CommandHandler("btcday", btcday))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# === START SCHEDULER ===
scheduler = BackgroundScheduler(timezone="Asia/Singapore")
scheduler.add_job(fetch_btc_price, 'cron', hour=12, minute=0)
scheduler.add_job(alert_if_above_target, 'interval', minutes=2)

# === RUN BOT ===
app.run_polling()

scheduler.start()
