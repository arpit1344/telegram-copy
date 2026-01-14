# admin_bot.py
import os, json, time, uuid, subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = "PASTE_BOT_TOKEN"
ADMIN_ID = 123456789
# ==================

def run(cmd):
    return subprocess.getoutput(cmd)

# ---------- WORKER AUTO-DETECT ----------
def worker_units():
    out = run("systemctl list-unit-files | grep telegram_worker@")
    if "telegram_worker@" in out:
        return ["telegram_worker@1", "telegram_worker@2"]
    return ["telegram_worker"]

def start_workers():
    for w in worker_units():
        run(f"sudo systemctl start {w}")

def stop_workers():
    for w in worker_units():
        run(f"sudo systemctl stop {w}")

def restart_workers():
    for w in worker_units():
        run(f"sudo systemctl restart {w}")

# ---------- HELPERS ----------
def progress_bar(percent, size=20):
    filled = int(size * percent / 100)
    return "█" * filled + "░" * (size - filled)

def fmt_eta(sec):
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
        return await func(update, context)
    return wrapper

# ---------- UI ----------
def main_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Job", callback_data="create")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="stats")],
        [InlineKeyboardButton("▶ Start Workers", callback_data="start_workers"),
         InlineKeyboardButton("♻ Restart Workers", callback_data="restart_workers")],
        [InlineKeyboardButton("🔁 Restart Admin Bot", callback_data="restart_admin")]
    ])

# ---------- COMMANDS ----------
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Admin Panel Ready", reply_markup=main_panel())

@admin_only
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # ---- WORKERS ----
    if q.data == "start_workers":
        start_workers()
        await q.edit_message_text("▶ Workers started", reply_markup=main_panel())

    elif q.data == "restart_workers":
        restart_workers()
        await q.edit_message_text("♻ Workers restarted", reply_markup=main_panel())

    elif q.data == "restart_admin":
        subprocess.Popen(["sudo", "systemctl", "restart", "telegram_admin"])

    # ---- DASHBOARD ----
    elif q.data == "stats":
        kb = []
        text = "📊 Jobs\n\n"

        for p in ["high", "normal", "low"]:
            folder = f"jobs/{p}"
            if not os.path.isdir(folder):
                continue

            for f in os.listdir(folder):
                if not f.endswith(".json"):
                    continue

                job = json.load(open(os.path.join(folder, f)))
                jid = job["id"]
                text += f"🆔 {jid} | {job.get('progress',0)}% | {job['status']}\n"
                kb.append([InlineKeyboardButton(f"🔍 View {jid}", callback_data=f"view:{p}:{f}")])

        kb.append([InlineKeyboardButton("⬅ Back", callback_data="back")])
        await q.edit_message_text(text or "No jobs", reply_markup=InlineKeyboardMarkup(kb))

    # ---- JOB DETAIL ----
    elif q.data.startswith("view:"):
        _, pr, fname = q.data.split(":")
        path = f"jobs/{pr}/{fname}"
        job = json.load(open(path))

        percent = job.get("progress", 0)
        text = (
            f"🆔 {job['id']}\n"
            f"{progress_bar(percent)} {percent}%\n\n"
            f"📦 {job.get('processed_items',0)} / {job.get('total_items',0)}\n"
            f"⚡ {job.get('speed',0)} msg/s\n"
            f"⏱ ETA: {fmt_eta(job.get('eta_seconds',0))}\n\n"
            f"🔁 Retries: {job.get('retry_count',0)} / {job.get('max_retries',3)}\n"
            f"📨 Batch size: {job.get('batch_size',10)}\n"
            f"🕒 Last msg id: {job.get('last_message_id',0)}\n\n"
            f"⚙ Status: {job['status']}"
        )

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏸ Pause", callback_data=f"pause:{pr}:{fname}"),
                InlineKeyboardButton("▶ Resume", callback_data=f"resume:{pr}:{fname}")
            ],
            [
                InlineKeyboardButton("🔄 Retry", callback_data=f"retry:{pr}:{fname}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete:{pr}:{fname}")
            ],
            [InlineKeyboardButton("⬅ Back", callback_data="stats")]
        ])

        await q.edit_message_text(text, reply_markup=kb)

    # ---- ACTIONS ----
    elif q.data.startswith("pause:"):
        _, pr, fname = q.data.split(":")
        path = f"jobs/{pr}/{fname}"
        job = json.load(open(path))
        job["status"] = "paused"
        json.dump(job, open(path, "w"), indent=2)
        await q.answer("⏸ Job paused")

    elif q.data.startswith("resume:"):
        _, pr, fname = q.data.split(":")
        path = f"jobs/{pr}/{fname}"
        job = json.load(open(path))
        job["status"] = "running"
        json.dump(job, open(path, "w"), indent=2)
        await q.answer("▶ Job resumed")

    elif q.data.startswith("retry:"):
        _, pr, fname = q.data.split(":")
        path = f"jobs/{pr}/{fname}"
        job = json.load(open(path))
        job["status"] = "running"
        job["retry_count"] = 0
        json.dump(job, open(path, "w"), indent=2)
        await q.answer("🔄 Job retry started")

    elif q.data.startswith("delete:"):
        _, pr, fname = q.data.split(":")
        os.remove(f"jobs/{pr}/{fname}")
        await q.answer("🗑 Job deleted")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    print("✅ Admin bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
