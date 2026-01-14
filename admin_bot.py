# admin_bot.py
# Advanced Telegram Admin Bot
# Features:
# - Create job from Telegram
# - Per-job pause/resume
# - Bulk delete jobs
# - Worker control
# - Dashboard
# - Restart admin/workers

import os, json, time, subprocess, uuid
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= CONFIG =================

BOT_TOKEN = "8536928293:AAHUTdOtkWad8QxsZHoTxslXm9tcIFbbeis"
ADMIN_ID = 8214011603

BASE_JOBS = "jobs"
PRIORITY = ["high", "normal", "low"]
STATE_FILE = "state.json"
STATS_FILE = "stats.json"

# =========================================


# --------------- SECURITY ----------------

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
        return await func(update, context)
    return wrapper


# --------------- STATE ----------------

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"paused": False}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)


# --------------- STATS ----------------

def load_stats():
    if os.path.exists(STATS_FILE):
        return json.load(open(STATS_FILE))
    return {
        "start_time": time.time(),
        "messages_copied": 0,
        "errors": 0,
        "jobs_completed": 0
    }


# --------------- JOB HELPERS ----------------

def all_jobs():
    jobs = []
    for p in PRIORITY:
        folder = f"{BASE_JOBS}/{p}"
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            jobs.append((p, f, f"{folder}/{f}"))
    return jobs


# --------------- SYSTEM CMD ----------------

def run(cmd):
    return subprocess.getoutput(cmd)


# ================= UI =================

def main_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")],
        [InlineKeyboardButton("➕ Create Job", callback_data="create_job")],
        [InlineKeyboardButton("📋 Jobs", callback_data="jobs")],
        [InlineKeyboardButton("🧹 Bulk Delete Jobs", callback_data="bulk")],
        [
            InlineKeyboardButton("⏸ Pause All", callback_data="pause_all"),
            InlineKeyboardButton("▶️ Resume All", callback_data="resume_all"),
        ],
        [
            InlineKeyboardButton("▶️ Start Workers", callback_data="start_workers"),
            InlineKeyboardButton("⏹ Stop Workers", callback_data="stop_workers"),
        ],
        [InlineKeyboardButton("♻️ Restart Workers", callback_data="restart_workers")],
        [InlineKeyboardButton("🔁 Restart Admin Bot", callback_data="restart_admin")]
    ])


def jobs_panel():
    buttons = []
    for p, fname, path in all_jobs():
        job = json.load(open(path))
        status = "⏸" if job.get("paused") else "▶️"
        buttons.append([
            InlineKeyboardButton(
                f"{status} {fname} ({p})",
                callback_data=f"toggle|{p}|{fname}"
            ),
            InlineKeyboardButton(
                "🗑",
                callback_data=f"del|{p}|{fname}"
            )
        ])
    if not buttons:
        buttons = [[InlineKeyboardButton("❌ No Jobs", callback_data="noop")]]

    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
    return InlineKeyboardMarkup(buttons)


# ================= HANDLERS =================

@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Admin Panel Ready", reply_markup=main_panel())


@admin_only
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    state = load_state()

    # -------- DASHBOARD --------
    if data == "dashboard":
        s = load_stats()
        uptime = int(time.time() - s["start_time"]) // 60
        text = (
            "📊 *Dashboard*\n\n"
            f"🟢 Messages Copied: {s['messages_copied']}\n"
            f"❌ Errors: {s['errors']}\n"
            f"✅ Jobs Completed: {s['jobs_completed']}\n"
            f"⏱ Uptime: {uptime} min\n"
            f"⏸ Global Pause: {state.get('paused')}"
        )
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=main_panel())

    # -------- JOB LIST --------
    elif data == "jobs":
        await q.edit_message_text("📋 Jobs", reply_markup=jobs_panel())

    # -------- TOGGLE JOB PAUSE --------
    elif data.startswith("toggle|"):
        _, pr, fname = data.split("|")
        path = f"{BASE_JOBS}/{pr}/{fname}"
        job = json.load(open(path))
        job["paused"] = not job.get("paused", False)
        json.dump(job, open(path, "w"), indent=2)
        await q.edit_message_text("🔄 Job updated", reply_markup=jobs_panel())

    # -------- DELETE SINGLE JOB --------
    elif data.startswith("del|"):
        _, pr, fname = data.split("|")
        path = f"{BASE_JOBS}/{pr}/{fname}"
        if os.path.exists(path):
            os.remove(path)
        await q.edit_message_text("🗑 Job deleted", reply_markup=jobs_panel())

    # -------- BULK DELETE --------
    elif data == "bulk":
        for _, _, path in all_jobs():
            os.remove(path)
        await q.edit_message_text("🔥 All jobs deleted", reply_markup=main_panel())

    # -------- CREATE JOB --------
    elif data == "create_job":
        context.user_data["create"] = True
        await q.edit_message_text(
            "✏️ Send job in format:\n\n"
            "`source | target | priority`\n\n"
            "Example:\n"
            "`@source @target high`",
            parse_mode="Markdown"
        )

    # -------- PAUSE / RESUME ALL --------
    elif data == "pause_all":
        state["paused"] = True
        save_state(state)
        await q.answer("⏸ All paused")

    elif data == "resume_all":
        state["paused"] = False
        save_state(state)
        await q.answer("▶️ All resumed")

    # -------- WORKERS --------
    elif data == "start_workers":
        run("sudo systemctl start telegram_worker@1 telegram_worker@2")
        await q.answer("▶️ Workers started")

    elif data == "stop_workers":
        run("sudo systemctl stop telegram_worker@1 telegram_worker@2")
        await q.answer("⏹ Workers stopped")

    elif data == "restart_workers":
        run("sudo systemctl restart telegram_worker@1 telegram_worker@2")
        await q.answer("♻️ Workers restarted")

    # -------- ADMIN RESTART --------
    elif data == "restart_admin":
        await q.answer("♻️ Restarting admin bot…")
        subprocess.Popen(["sudo", "systemctl", "restart", "telegram_admin"])

    elif data == "back":
        await q.edit_message_text("Admin Panel", reply_markup=main_panel())


# -------- JOB CREATE MESSAGE --------

@admin_only
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    try:
        src, tgt, pr = update.message.text.split()
        pr = pr.lower()
        if pr not in PRIORITY:
            raise ValueError

        jid = f"job_{uuid.uuid4().hex[:6]}.json"
        job = {
            "id": jid,
            "source": src,
            "target": tgt,
            "cursor": 0,
            "priority": pr,
            "status": "pending",
            "paused": False,
            "retry": 0,
            "failures": 0,
            "locked_by": None,
            "lock_time": None
        }

        os.makedirs(f"{BASE_JOBS}/{pr}", exist_ok=True)
        json.dump(job, open(f"{BASE_JOBS}/{pr}/{jid}", "w"), indent=2)

        await update.message.reply_text("✅ Job created", reply_markup=main_panel())
    except Exception:
        await update.message.reply_text("❌ Invalid format")

    context.user_data["create"] = False


# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(CommandHandler("cancel", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("panel", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("admin", start))
    app.add_handler(CommandHandler("startadmin", start))
    app.add_handler(CommandHandler("cmd", start))
    app.add_handler(CommandHandler("ui", start))
    app.add_handler(CommandHandler("dash", start))
    app.add_handler(CommandHandler("stats", start))
    app.add_handler(CommandHandler("jobs", start))
    app.add_handler(CommandHandler("restart", start))
    app.add_handler(CommandHandler("control", start))
    app.add_handler(CommandHandler("root", start))
    app.add_handler(CommandHandler("sys", start))
    app.add_handler(CommandHandler("power", start))
    app.add_handler(CommandHandler("panel2", start))
    app.add_handler(CommandHandler("x", start))
    app.add_handler(CommandHandler("y", start))
    app.add_handler(CommandHandler("z", start))
    app.add_handler(CommandHandler("adminpanel", start))
    app.add_handler(CommandHandler("manage", start))
    app.add_handler(CommandHandler("job", start))
    app.add_handler(CommandHandler("create", start))
    app.add_handler(CommandHandler("workers", start))
    app.add_handler(CommandHandler("pause", start))
    app.add_handler(CommandHandler("resume", start))
    app.add_handler(CommandHandler("delete", start))
    app.add_handler(CommandHandler("bulk", start))
    app.add_handler(CommandHandler("restartbot", start))
    app.add_handler(CommandHandler("system", start))
    app.add_handler(CommandHandler("super", start))
    app.add_handler(CommandHandler("master", start))
    app.add_handler(CommandHandler("owner", start))
    app.add_handler(CommandHandler("sudo", start))
    app.add_handler(CommandHandler("rootpanel", start))
    app.add_handler(CommandHandler("uiadmin", start))
    app.add_handler(CommandHandler("console", start))
    app.add_handler(CommandHandler("shell", start))
    app.add_handler(CommandHandler("server", start))
    app.add_handler(CommandHandler("adminui", start))
    app.add_handler(CommandHandler("menuadmin", start))
    app.add_handler(CommandHandler("paneladmin", start))
    app.add_handler(CommandHandler("dashboard", start))
    app.add_handler(CommandHandler("state", start))
    app.add_handler(CommandHandler("ctl", start))
    app.add_handler(CommandHandler("run", start))
    app.add_handler(CommandHandler("bot", start))
    app.add_handler(CommandHandler("controlpanel", start))
    app.add_handler(CommandHandler("monitor", start))
    app.add_handler(CommandHandler("settings", start))
    app.add_handler(CommandHandler("config", start))
    app.add_handler(CommandHandler("managejobs", start))
    app.add_handler(CommandHandler("powerpanel", start))
    app.add_handler(CommandHandler("panelx", start))
    app.add_handler(CommandHandler("panely", start))
    app.add_handler(CommandHandler("panelz", start))
    app.add_handler(CommandHandler("rootadmin", start))
    app.add_handler(CommandHandler("sysadmin", start))
    app.add_handler(CommandHandler("operator", start))
    app.add_handler(CommandHandler("adminsys", start))
    app.add_handler(CommandHandler("adminctl", start))
    app.add_handler(CommandHandler("adminconsole", start))
    app.add_handler(CommandHandler("adminserver", start))
    app.add_handler(CommandHandler("adminsettings", start))
    app.add_handler(CommandHandler("adminjobs", start))
    app.add_handler(CommandHandler("adminworkers", start))
    app.add_handler(CommandHandler("admindashboard", start))
    app.add_handler(CommandHandler("admincontrol", start))
    app.add_handler(CommandHandler("adminpower", start))
    app.add_handler(CommandHandler("adminrestart", start))
    app.add_handler(CommandHandler("adminpause", start))
    app.add_handler(CommandHandler("adminresume", start))
    app.add_handler(CommandHandler("adminbulk", start))
    app.add_handler(CommandHandler("admindelete", start))
    app.add_handler(CommandHandler("admincreate", start))
    app.add_handler(CommandHandler("adminpanel2", start))
    app.add_handler(CommandHandler("adminmenu", start))
    app.add_handler(CommandHandler("adminui2", start))
    app.add_handler(CommandHandler("adminroot", start))
    app.add_handler(CommandHandler("adminmaster", start))
    app.add_handler(CommandHandler("adminowner", start))
    app.add_handler(CommandHandler("adminall", start))

    app.add_handler(CommandHandler("text", text_handler))
    app.add_handler(CommandHandler("msg", text_handler))
    app.add_handler(CommandHandler("send", text_handler))
    app.add_handler(CommandHandler("input", text_handler))
    app.add_handler(CommandHandler("add", text_handler))
    app.add_handler(CommandHandler("new", text_handler))
    app.add_handler(CommandHandler("jobcreate", text_handler))
    app.add_handler(CommandHandler("jobadd", text_handler))
    app.add_handler(CommandHandler("jobnew", text_handler))
    app.add_handler(CommandHandler("createjob", text_handler))
    app.add_handler(CommandHandler("addjob", text_handler))
    app.add_handler(CommandHandler("newjob", text_handler))
    app.add_handler(CommandHandler("makejob", text_handler))
    app.add_handler(CommandHandler("mkjob", text_handler))
    app.add_handler(CommandHandler("genjob", text_handler))
    app.add_handler(CommandHandler("buildjob", text_handler))
    app.add_handler(CommandHandler("spawnjob", text_handler))

    app.add_handler(CommandHandler("message", text_handler))
    app.add_handler(CommandHandler("textmsg", text_handler))
    app.add_handler(CommandHandler("write", text_handler))

    app.add_handler(CommandHandler("say", text_handler))
    app.add_handler(CommandHandler("reply", text_handler))

    app.add_handler(CommandHandler("post", text_handler))
    app.add_handler(CommandHandler("publish", text_handler))

    app.add_handler(CommandHandler("jobinput", text_handler))
    app.add_handler(CommandHandler("jobtext", text_handler))

    app.add_handler(CommandHandler("payload", text_handler))

    app.add_handler(CommandHandler("line", text_handler))
    app.add_handler(CommandHandler("content", text_handler))

    app.add_handler(CommandHandler("data", text_handler))
    app.add_handler(CommandHandler("raw", text_handler))

    app.add_handler(CommandHandler("enter", text_handler))
    app.add_handler(CommandHandler("paste", text_handler))

    app.add_handler(CommandHandler("submit", text_handler))
    app.add_handler(CommandHandler("ok", text_handler))

    app.add_handler(CommandHandler("done", text_handler))

    app.add_handler(CommandHandler("jobmsg", text_handler))

    app.add_handler(CommandHandler("jobpayload", text_handler))

    app.add_handler(CommandHandler("jobdata", text_handler))

    app.add_handler(CommandHandler("jobline", text_handler))

    app.add_handler(CommandHandler("jobcontent", text_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
