import os, json, uuid, subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

CFG = json.load(open("config.json"))
ADMIN_ID = CFG["admin_id"]

STATE = {}
os.makedirs("jobs", exist_ok=True)
os.makedirs("logs", exist_ok=True)

def kb(r): return InlineKeyboardMarkup(r)
def jp(jid): return f"jobs/{jid}.json"
def load(jid): return json.load(open(jp(jid)))
def save(j): json.dump(j, open(jp(j["job_id"]), "w"), indent=2)

def progress(job):
    d = job["progress"]["done"]
    t = job["progress"]["total"]
    p = int((d/t)*100) if t else 0
    return f"{d}/{t} ({p}%)"

async def home(msg):
    await msg.reply_text(
        "🛠 Telegram Copier Admin",
        reply_markup=kb([
            [InlineKeyboardButton("➕ Create Job", callback_data="create")],
            [InlineKeyboardButton("📋 Jobs", callback_data="list")],
            [InlineKeyboardButton("▶ Run", callback_data="run")]
        ])
    )

async def start(update: Update, ctx):
    if update.effective_user.id != ADMIN_ID: return
    STATE.clear()
    await home(update.message)

async def buttons(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    d = q.data

    if d == "home":
        STATE.clear()
        await home(q.message)

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
        await q.message.reply_text("Send job title")

    elif d == "run":
        subprocess.Popen(["python3", "job_runner.py"])
        await q.message.reply_text("Runner started")

    elif d == "list":
        rows = []
        for f in os.listdir("jobs"):
            jid = f.replace(".json", "")
            rows.append([InlineKeyboardButton(jid, callback_data=f"open_{jid}")])
        rows.append([InlineKeyboardButton("⬅ Back", callback_data="home")])
        await q.message.reply_text("Jobs:", reply_markup=kb(rows))

    elif d.startswith("open_"):
        jid = d.replace("open_", "")
        STATE["job"] = jid
        job = load(jid)
        await q.message.reply_text(
            f"{job['title']}\nStatus: {job['status']}\nProgress: {progress(job)}",
            reply_markup=kb([
                [InlineKeyboardButton("⏸ Pause" if not job["paused"] else "▶ Resume", callback_data="toggle")],
                [InlineKeyboardButton("🧾 Logs", callback_data="logs"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                [InlineKeyboardButton("⬅ Back", callback_data="list")]
            ])
        )

    elif d == "toggle":
        job = load(STATE["job"])
        job["paused"] = not job["paused"]
        job["status"] = "paused" if job["paused"] else "running"
        save(job)
        await q.message.reply_text("Status updated")

    elif d == "cancel":
        job = load(STATE["job"])
        job["cancelled"] = True
        job["status"] = "cancelled"
        save(job)
        await q.message.reply_text("Cancelled")

    elif d == "logs":
        jid = STATE["job"]
        path = f"logs/{jid}.log"
        txt = open(path).read()[-1500:] if os.path.exists(path) else "No logs"
        await q.message.reply_text(f"Logs:\n{txt}")

async def text(update: Update, ctx):
    if update.effective_user.id != ADMIN_ID: return
    step = STATE.get("step")
    job = STATE.get("job")

    if step == "title":
        job["title"] = update.message.text
        STATE["step"] = "sources"
        await update.message.reply_text("Send source channel, `done` when finished")

    elif step == "sources":
        if update.message.text.lower() == "done":
            STATE["step"] = "destinations"
            await update.message.reply_text("Send destination channel, `done` when finished")
        else:
            job["sources"].append(update.message.text)

    elif step == "destinations":
        if update.message.text.lower() == "done":
            save(job)
            STATE.clear()
            await update.message.reply_text("Job created")
            await home(update.message)
        else:
            job["destinations"].append(update.message.text)

app = ApplicationBuilder().token("8536928293:AAHUTdOtkWad8QxsZHoTxslXm9tcIFbbeis").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
app.run_polling()
