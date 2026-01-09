import os
import json
import uuid
import subprocess
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from telethon import TelegramClient
from telethon.tl.types import MessageService
from dateutil.parser import parse

# ================= CONFIG =================
CFG = json.load(open("config.json"))
ADMIN_ID = CFG["admin_id"]
API_ID = CFG["api_id"]
API_HASH = CFG["api_hash"]

JOBS_DIR = "jobs"
LOGS_DIR = "logs"

os.makedirs(JOBS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

STATE = {}

# ================= HELPERS =================
def kb(rows):
    return InlineKeyboardMarkup(rows)

def job_path(jid):
    return f"{JOBS_DIR}/{jid}.json"

def load_job(jid):
    return json.load(open(job_path(jid)))

def save_job(job):
    with open(job_path(job["job_id"]), "w") as f:
        json.dump(job, f, indent=2)

def progress_text(job):
    done = job["progress"]["done"]
    total = job["progress"]["total"]
    pct = int((done / total) * 100) if total else 0
    return f"{done}/{total} ({pct}%)"

# ================= TOTAL COUNT LOGIC =================
async def calculate_total_messages(job):
    client = TelegramClient("count_session", API_ID, API_HASH)
    await client.start()

    total = 0

    for src in job["sources"]:
        async for msg in client.iter_messages(src):
            if isinstance(msg, MessageService):
                continue

            if job["date_mode"] != "all":
                mdate = msg.date.date()
                if job["date_mode"] == "single":
                    if mdate != parse(job["from"]).date():
                        continue
                if job["date_mode"] == "range":
                    if not (parse(job["from"]).date() <= mdate <= parse(job["to"]).date()):
                        continue

            total += 1

    await client.disconnect()
    return total

# ================= UI =================
async def home(msg):
    await msg.reply_text(
        "🛠 *Telegram Copier – Admin Panel*",
        parse_mode="Markdown",
        reply_markup=kb([
            [InlineKeyboardButton("➕ Create Job", callback_data="create")],
            [InlineKeyboardButton("📋 Job List", callback_data="list")],
            [InlineKeyboardButton("▶ Run Job Runner", callback_data="run")]
        ])
    )

# ================= COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    STATE.clear()
    await home(update.message)

# ================= CALLBACKS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    d = q.data

    # -------- HOME --------
    if d == "home":
        STATE.clear()
        await home(q.message)

    # -------- CREATE JOB --------
    elif d == "create":
        STATE.clear()
        STATE["step"] = "title"
        STATE["job"] = {
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
        await q.message.reply_text("📝 Send Job Title")

    # -------- LIST JOBS --------
    elif d == "list":
        files = os.listdir(JOBS_DIR)
        if not files:
            await q.message.reply_text("No jobs found", reply_markup=kb([
                [InlineKeyboardButton("⬅ Back", callback_data="home")]
            ]))
            return

        rows = []
        for f in files:
            jid = f.replace(".json", "")
            rows.append([InlineKeyboardButton(jid, callback_data=f"open_{jid}")])
        rows.append([InlineKeyboardButton("⬅ Back", callback_data="home")])

        await q.message.reply_text("📋 Jobs", reply_markup=kb(rows))

    # -------- OPEN JOB --------
    elif d.startswith("open_"):
        jid = d.replace("open_", "")
        STATE["job"] = jid
        job = load_job(jid)

        await q.message.reply_text(
            f"""📌 *{job['title']}*

Status: `{job['status']}`
Progress: `{progress_text(job)}`
Sources: `{len(job['sources'])}`
Destinations: `{len(job['destinations'])}`
Batch: `{job['batch']}`
Date mode: `{job['date_mode']}`
""",
            parse_mode="Markdown",
            reply_markup=kb([
                [InlineKeyboardButton("➕ Add Source", callback_data="add_source")],
                [InlineKeyboardButton("📥 Set Destination", callback_data="add_dest")],
                [InlineKeyboardButton("📅 Date Filter", callback_data="date_menu")],
                [InlineKeyboardButton("🔢 Batch Size", callback_data="batch_menu")],
                [InlineKeyboardButton("▶ Start Job", callback_data="start_job")],
                [InlineKeyboardButton("⏸ Pause/Resume", callback_data="toggle")],
                [InlineKeyboardButton("📊 Progress", callback_data="progress")],
                [InlineKeyboardButton("🧾 Logs", callback_data="logs")],
                [InlineKeyboardButton("❌ Cancel Job", callback_data="cancel")],
                [InlineKeyboardButton("⬅ Back", callback_data="list")]
            ])
        )

    # -------- ADD SOURCE --------
    elif d == "add_source":
        STATE["step"] = "add_source"
        await q.message.reply_text("Send source channel (username / link). Send `done` to finish")

    # -------- ADD DEST --------
    elif d == "add_dest":
        STATE["step"] = "add_dest"
        await q.message.reply_text("Send destination channel (username / link). Send `done` to finish")

    # -------- DATE MENU --------
    elif d == "date_menu":
        await q.message.reply_text(
            "Select date mode",
            reply_markup=kb([
                [InlineKeyboardButton("All Messages", callback_data="date_all")],
                [InlineKeyboardButton("Single Date", callback_data="date_single")],
                [InlineKeyboardButton("Date Range", callback_data="date_range")],
                [InlineKeyboardButton("⬅ Back", callback_data=f"open_{STATE['job']}")]
            ])
        )

    elif d == "date_all":
        job = load_job(STATE["job"])
        job["date_mode"] = "all"
        job["from"] = None
        job["to"] = None
        save_job(job)
        await q.message.reply_text("Date mode set to ALL")

    elif d == "date_single":
        STATE["step"] = "date_single"
        await q.message.reply_text("Send date YYYY-MM-DD")

    elif d == "date_range":
        STATE["step"] = "date_from"
        await q.message.reply_text("Send FROM date YYYY-MM-DD")

    # -------- BATCH MENU --------
    elif d == "batch_menu":
        await q.message.reply_text(
            "Select batch size",
            reply_markup=kb([
                [InlineKeyboardButton("10", callback_data="batch_10"),
                 InlineKeyboardButton("20", callback_data="batch_20"),
                 InlineKeyboardButton("30", callback_data="batch_30")],
                [InlineKeyboardButton("Custom", callback_data="batch_custom")],
                [InlineKeyboardButton("⬅ Back", callback_data=f"open_{STATE['job']}")]
            ])
        )

    elif d.startswith("batch_"):
        job = load_job(STATE["job"])
        val = d.split("_")[1]
        if val == "custom":
            STATE["step"] = "batch_custom"
            await q.message.reply_text("Send custom batch number")
        else:
            job["batch"] = int(val)
            save_job(job)
            await q.message.reply_text(f"Batch size set to {val}")

    # -------- START JOB (REAL LOGIC) --------
    elif d == "start_job":
        jid = STATE["job"]
        job = load_job(jid)

        if not job["sources"]:
            await q.message.reply_text("❌ No sources added")
            return
        if not job["destinations"]:
            await q.message.reply_text("❌ No destinations added")
            return

        await q.message.reply_text("⏳ Calculating total messages, please wait...")

        total = await calculate_total_messages(job)

        if total == 0:
            await q.message.reply_text("❌ No messages found with selected filters")
            return

        job["progress"]["done"] = 0
        job["progress"]["total"] = total
        job["status"] = "running"
        job["paused"] = False
        job["cancelled"] = False
        save_job(job)

        subprocess.Popen(["python3", "job_runner.py"])

        await q.message.reply_text(f"▶ Job started\nTotal messages: {total}")

    # -------- TOGGLE PAUSE --------
    elif d == "toggle":
        job = load_job(STATE["job"])
        job["paused"] = not job["paused"]
        job["status"] = "paused" if job["paused"] else "running"
        save_job(job)
        await q.message.reply_text("⏯ Status updated")

    # -------- PROGRESS --------
    elif d == "progress":
        job = load_job(STATE["job"])
        await q.message.reply_text(
            f"📊 Progress\n{progress_text(job)}"
        )

    # -------- LOGS --------
    elif d == "logs":
        jid = STATE["job"]
        path = f"{LOGS_DIR}/{jid}.log"
        if not os.path.exists(path):
            txt = "No logs yet"
        else:
            txt = "".join(open(path).readlines()[-20:])
        await q.message.reply_text(f"🧾 Logs\n\n{txt}")

    # -------- CANCEL --------
    elif d == "cancel":
        job = load_job(STATE["job"])
        job["cancelled"] = True
        job["status"] = "cancelled"
        save_job(job)
        await q.message.reply_text("❌ Job cancelled")

    # -------- RUN RUNNER --------
    elif d == "run":
        subprocess.Popen(["python3", "job_runner.py"])
        await q.message.reply_text("Job runner started")

# ================= TEXT INPUT =================
async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    step = STATE.get("step")
    job = STATE.get("job")

    if step == "title":
        job["title"] = update.message.text
        STATE["step"] = "add_source"
        await update.message.reply_text("Send source channel (send `done` to finish)")

    elif step == "add_source":
        if update.message.text.lower() == "done":
            STATE["step"] = None
            save_job(job)
            await update.message.reply_text("Sources saved")
        else:
            job["sources"].append(update.message.text)

    elif step == "add_dest":
        if update.message.text.lower() == "done":
            STATE["step"] = None
            save_job(job)
            await update.message.reply_text("Destinations saved")
        else:
            job["destinations"].append(update.message.text)

    elif step == "date_single":
        job = load_job(STATE["job"])
        job["date_mode"] = "single"
        job["from"] = update.message.text
        save_job(job)
        STATE["step"] = None
        await update.message.reply_text("Single date set")

    elif step == "date_from":
        job = load_job(STATE["job"])
        job["from"] = update.message.text
        STATE["step"] = "date_to"
        save_job(job)
        await update.message.reply_text("Send TO date YYYY-MM-DD")

    elif step == "date_to":
        job = load_job(STATE["job"])
        job["to"] = update.message.text
        job["date_mode"] = "range"
        save_job(job)
        STATE["step"] = None
        await update.message.reply_text("Date range set")

    elif step == "batch_custom":
        job = load_job(STATE["job"])
        job["batch"] = int(update.message.text)
        save_job(job)
        STATE["step"] = None
        await update.message.reply_text("Custom batch set")

# ================= APP =================
app = ApplicationBuilder().token(CFG["admin_bot_token"]).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

app.run_polling()
