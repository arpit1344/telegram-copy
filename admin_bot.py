import os, json, uuid, subprocess, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)
from telethon import TelegramClient
from telethon.tl.types import MessageService
from dateutil.parser import parse

# ========= CONFIG =========
CFG = json.load(open("config.json"))
ADMIN_ID = CFG["admin_id"]
API_ID = CFG["api_id"]
API_HASH = CFG["api_hash"]

JOBS_DIR = "jobs"
LOGS_DIR = "logs"
os.makedirs(JOBS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

STATE = {
    "step": None,
    "job_data": None,
    "job_id": None
}

# ========= HELPERS =========
def kb(r): return InlineKeyboardMarkup(r)
def jp(jid): return f"{JOBS_DIR}/{jid}.json"
def load(jid): return json.load(open(jp(jid)))
def save(job): json.dump(job, open(jp(job["job_id"]), "w"), indent=2)

def progress(job):
    d, t = job["progress"]["done"], job["progress"]["total"]
    return f"{d}/{t} ({int(d/t*100) if t else 0}%)"

# ========= TOTAL COUNT =========
async def count_msgs(job):
    client = TelegramClient("count_session", API_ID, API_HASH)
    await client.start()
    total = 0

    for src in job["sources"]:
        async for msg in client.iter_messages(src):
            if isinstance(msg, MessageService):
                continue

            if job["date_mode"] != "all":
                m = msg.date.date()
                if job["date_mode"] == "single":
                    if m != parse(job["from"]).date():
                        continue
                if job["date_mode"] == "range":
                    if not (parse(job["from"]).date() <= m <= parse(job["to"]).date()):
                        continue
            total += 1

    await client.disconnect()
    return total

# ========= UI =========
async def home(msg):
    await msg.reply_text(
        "🛠 *Telegram Copier – Admin Panel*",
        parse_mode="Markdown",
        reply_markup=kb([
            [InlineKeyboardButton("➕ Create Job", callback_data="create")],
            [InlineKeyboardButton("📋 Job List", callback_data="list")]
        ])
    )

# ========= START =========
async def start(update: Update, ctx):
    if update.effective_user.id != ADMIN_ID:
        return
    STATE["step"] = None
    STATE["job_data"] = None
    STATE["job_id"] = None
    await home(update.message)

# ========= BUTTON HANDLER =========
async def buttons(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        return

    d = q.data

    # CREATE JOB
    if d == "create":
        STATE["step"] = "title"
        STATE["job_data"] = {
            "job_id": f"job_{uuid.uuid4().hex[:6]}",
            "title": "",
            "sources": [],
            "destinations": [],
            "date_mode": "all",
            "from": None,
            "to": None,
            "batch": 10,
            "status": "created",
            "progress": {"done": 0, "total": 0},
            "resume": {},
            "paused": False,
            "cancelled": False
        }
        await q.message.reply_text("📝 Send job title")

    # LIST JOBS
    elif d == "list":
        rows = [[InlineKeyboardButton(f.replace(".json",""), callback_data=f"open_{f.replace('.json','')}")]
                for f in os.listdir(JOBS_DIR)]
        rows.append([InlineKeyboardButton("⬅ Back", callback_data="home")])
        await q.message.reply_text("📋 Jobs:", reply_markup=kb(rows))

    # OPEN JOB
    elif d.startswith("open_"):
        jid = d.replace("open_", "")
        STATE["job_id"] = jid
        job = load(jid)

        await q.message.reply_text(
            f"""📌 *{job['title']}*

Status: `{job['status']}`
Progress: `{progress(job)}`
Batch: `{job['batch']}`
Date Mode: `{job['date_mode']}`
""",
            parse_mode="Markdown",
            reply_markup=kb([
                [InlineKeyboardButton("📆 Date Filter", callback_data="date_menu")],
                [InlineKeyboardButton("🔢 Batch Size", callback_data="batch_menu")],
                [InlineKeyboardButton("📊 Live Progress", callback_data="live")],
                [InlineKeyboardButton("▶ Start Job", callback_data="start_job")],
                [InlineKeyboardButton("⬅ Back", callback_data="list")]
            ])
        )

    # DATE MENU
    elif d == "date_menu":
        await q.message.reply_text(
            "📆 Select date filter",
            reply_markup=kb([
                [InlineKeyboardButton("All Messages", callback_data="date_all")],
                [InlineKeyboardButton("Single Date", callback_data="date_single")],
                [InlineKeyboardButton("Date Range", callback_data="date_range")],
                [InlineKeyboardButton("⬅ Back", callback_data=f"open_{STATE['job_id']}")]
            ])
        )

    elif d == "date_all":
        job = load(STATE["job_id"])
        job["date_mode"] = "all"
        job["from"] = job["to"] = None
        save(job)
        await q.message.reply_text("✅ Date filter set: ALL")

    elif d == "date_single":
        STATE["step"] = "date_single"
        await q.message.reply_text("Send date (YYYY-MM-DD)")

    elif d == "date_range":
        STATE["step"] = "date_from"
        await q.message.reply_text("Send FROM date (YYYY-MM-DD)")

    # BATCH MENU
    elif d == "batch_menu":
        await q.message.reply_text(
            "🔢 Select batch size",
            reply_markup=kb([
                [InlineKeyboardButton("10", callback_data="batch_10"),
                 InlineKeyboardButton("20", callback_data="batch_20"),
                 InlineKeyboardButton("30", callback_data="batch_30")],
                [InlineKeyboardButton("Custom", callback_data="batch_custom")],
                [InlineKeyboardButton("⬅ Back", callback_data=f"open_{STATE['job_id']}")]
            ])
        )

    elif d.startswith("batch_"):
        job = load(STATE["job_id"])
        val = d.split("_")[1]
        if val == "custom":
            STATE["step"] = "batch_custom"
            await q.message.reply_text("Send custom batch number")
        else:
            job["batch"] = int(val)
            save(job)
            await q.message.reply_text(f"✅ Batch set to {val}")

    # LIVE PROGRESS
    elif d == "live":
        job = load(STATE["job_id"])
        await q.message.reply_text(
            f"📊 *Live Progress*\n\nStatus: `{job['status']}`\nProgress: `{progress(job)}`",
            parse_mode="Markdown",
            reply_markup=kb([
                [InlineKeyboardButton("🔄 Refresh", callback_data="live")],
                [InlineKeyboardButton("⬅ Back", callback_data=f"open_{STATE['job_id']}")]
            ])
        )

    # START JOB
    elif d == "start_job":
        job = load(STATE["job_id"])
        await q.message.reply_text("⏳ Calculating total messages...")
        total = await count_msgs(job)
        job["progress"]["total"] = total
        job["status"] = "running"
        save(job)
        subprocess.Popen(["python3", "job_runner.py"])
        await q.message.reply_text(f"▶ Job started\nTotal messages: {total}")

# ========= TEXT HANDLER =========
async def text(update: Update, ctx):
    if update.effective_user.id != ADMIN_ID:
        return

    step = STATE["step"]
    job = STATE["job_data"]

    if step == "title":
        job["title"] = update.message.text
        STATE["step"] = "add_source"
        await update.message.reply_text("Send source channel (`done` to finish)")

    elif step == "add_source":
        if update.message.text.lower() == "done":
            STATE["step"] = "add_dest"
            await update.message.reply_text("Send destination channel (`done` to finish)")
        else:
            job["sources"].append(update.message.text)

    elif step == "add_dest":
        if update.message.text.lower() == "done":
            save(job)
            STATE["step"] = None
            STATE["job_data"] = None
            await update.message.reply_text("✅ Job created")
            await home(update.message)
        else:
            job["destinations"].append(update.message.text)

    elif step == "date_single":
        job = load(STATE["job_id"])
        job["date_mode"] = "single"
        job["from"] = update.message.text
        save(job)
        STATE["step"] = None
        await update.message.reply_text("✅ Single date set")

    elif step == "date_from":
        job = load(STATE["job_id"])
        job["from"] = update.message.text
        STATE["step"] = "date_to"
        save(job)
        await update.message.reply_text("Send TO date (YYYY-MM-DD)")

    elif step == "date_to":
        job = load(STATE["job_id"])
        job["to"] = update.message.text
        job["date_mode"] = "range"
        save(job)
        STATE["step"] = None
        await update.message.reply_text("✅ Date range set")

    elif step == "batch_custom":
        job = load(STATE["job_id"])
        job["batch"] = int(update.message.text)
        save(job)
        STATE["step"] = None
        await update.message.reply_text("✅ Custom batch set")

# ========= APP =========
app = ApplicationBuilder().token(CFG["admin_bot_token"]).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
app.run_polling()
