# admin_bot.py
import os, json, time, uuid, subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============ CONFIG ============
BOT_TOKEN = "8536928293:AAHUTdOtkWad8QxsZHoTxslXm9tcIFbbeis" 
ADMIN_ID = 8214011603
# ================================

# -------- GLOBAL STATE (Wizard) --------
JOB_WIZARD = {}
# --------------------------------------

def run(cmd):
    return subprocess.getoutput(cmd)

# -------- WORKER AUTO-DETECT --------
def worker_units():
    out = run("systemctl list-unit-files | grep telegram_worker@")
    if "telegram_worker@" in out:
        return ["telegram_worker@1", "telegram_worker@2"]
    return ["telegram_worker"]

def start_workers():
    for w in worker_units():
        run(f"sudo systemctl start {w}")

def restart_workers():
    for w in worker_units():
        run(f"sudo systemctl restart {w}")

# -------- HELPERS --------
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

# -------- UI --------
def main_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Job", callback_data="create_job")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="stats")],
        [InlineKeyboardButton("▶ Start Workers", callback_data="start_workers"),
         InlineKeyboardButton("♻ Restart Workers", callback_data="restart_workers")],
        [InlineKeyboardButton("🔁 Restart Admin Bot", callback_data="restart_admin")]
    ])

# -------- COMMANDS --------
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Admin Panel Ready", reply_markup=main_panel())

# -------- BUTTON HANDLER --------
@admin_only
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # ----- WORKERS -----
    if q.data == "start_workers":
        start_workers()
        await q.edit_message_text("▶ Workers started", reply_markup=main_panel())

    elif q.data == "restart_workers":
        restart_workers()
        await q.edit_message_text("♻ Workers restarted", reply_markup=main_panel())

    elif q.data == "restart_admin":
        subprocess.Popen(["sudo", "systemctl", "restart", "telegram_admin"])

    # ----- CREATE JOB WIZARD -----
    elif q.data == "create_job":
        JOB_WIZARD[q.from_user.id] = {"step": 1}
        await q.edit_message_text(
            "🧙‍♂️ Job Create Wizard\n\n"
            "Step 1️⃣\n"
            "Send SOURCE channel\n"
            "Example:\n"
            "@source_channel"
        )

    # ----- DASHBOARD -----
    elif q.data == "stats":
        text = "📊 Jobs\n\n"
        kb = []

        for p in ["high", "normal", "low"]:
            folder = f"jobs/{p}"
            if not os.path.isdir(folder):
                continue

            for f in os.listdir(folder):
                if not f.endswith(".json"):
                    continue

                job = json.load(open(os.path.join(folder, f)))
                text += f"🆔 {job['id']} | {job.get('progress',0)}% | {job['status']}\n"
                kb.append([InlineKeyboardButton(
                    f"🔍 View {job['id']}",
                    callback_data=f"view:{p}:{f}"
                )])

        kb.append([InlineKeyboardButton("⬅ Back", callback_data="back")])
        await q.edit_message_text(text or "No jobs", reply_markup=InlineKeyboardMarkup(kb))

    elif q.data == "back":
        await q.edit_message_text("⬅ Back to panel", reply_markup=main_panel())

# -------- TEXT HANDLER (Wizard Logic) --------
@admin_only
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in JOB_WIZARD:
        return

    wiz = JOB_WIZARD[uid]
    msg = update.message.text.strip()

    # STEP 1: SOURCE
    if wiz["step"] == 1:
        if not msg.startswith("@"):
            await update.message.reply_text("❌ Invalid source. Must start with @")
            return
        wiz["source"] = msg
        wiz["step"] = 2
        await update.message.reply_text(
            "Step 2️⃣\nSend TARGET channel\nExample:\n@target_channel"
        )

    # STEP 2: TARGET
    elif wiz["step"] == 2:
        if not msg.startswith("@") or msg == wiz["source"]:
            await update.message.reply_text("❌ Invalid target channel")
            return
        wiz["target"] = msg
        wiz["step"] = 3
        await update.message.reply_text(
            "Step 3️⃣\nSend PRIORITY\nhigh | normal | low"
        )

    # STEP 3: PRIORITY
    elif wiz["step"] == 3:
        if msg not in ("high", "normal", "low"):
            await update.message.reply_text("❌ Invalid priority")
            return
        wiz["priority"] = msg
        wiz["step"] = 4
        await update.message.reply_text(
            "Step 4️⃣\nSend BATCH SIZE (number)\nExample: 10"
        )

    # STEP 4: BATCH SIZE → CREATE JOB
    elif wiz["step"] == 4:
        if not msg.isdigit() or int(msg) <= 0:
            await update.message.reply_text("❌ Batch size must be a number")
            return

        batch = int(msg)
        pr = wiz["priority"]
        os.makedirs(f"jobs/{pr}", exist_ok=True)

        job = {
            "id": f"job_{uuid.uuid4().hex[:6]}",
            "source": wiz["source"],
            "target": wiz["target"],
            "priority": pr,
            "status": "running",

            "batch_size": batch,
            "processed_items": 0,
            "total_items": 0,
            "progress": 0,
            "last_message_id": 0,

            "retry_count": 0,
            "max_retries": 3,

            "created_at": int(time.time())
        }

        path = f"jobs/{pr}/{job['id']}.json"
        json.dump(job, open(path, "w"), indent=2)

        JOB_WIZARD.pop(uid, None)

        await update.message.reply_text(
            f"✅ Job Created Successfully\n\n"
            f"🆔 {job['id']}\n"
            f"📦 Batch size: {batch}",
            reply_markup=main_panel()
        )

# -------- MAIN --------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("✅ Admin bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
