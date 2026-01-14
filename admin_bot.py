# ================== admin_bot.py ==================
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

from config import BOT_TOKEN, ADMIN_ID, ALIASES_FILE, JOBS_DIR

# ================= GLOBAL =================
JOB_WIZARD = {}
# ==========================================

# ================= UTIL ===================
def run(cmd):
    return subprocess.getoutput(cmd)

def load_aliases():
    if not os.path.exists(ALIASES_FILE):
        return {}
    return json.load(open(ALIASES_FILE))

def save_aliases(data):
    json.dump(data, open(ALIASES_FILE, "w"), indent=2)

def resolve_alias(v):
    return load_aliases().get(v, v)

def valid_channel(v):
    if v.startswith("@") and len(v) > 1:
        return True
    if v.startswith("-100") and v[4:].isdigit():
        return True
    return False
# ==========================================

# ================= HELPERS =================
def progress_bar(percent, size=20):
    filled = int(size * percent / 100)
    return "█" * filled + "░" * (size - filled)

def fmt_eta(sec):
    if not sec:
        return "--"
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
# ===========================================

# ================= UI ======================
def main_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Job", callback_data="create_job")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")],
        [
            InlineKeyboardButton("▶ Start Workers", callback_data="start_workers"),
            InlineKeyboardButton("♻ Restart Workers", callback_data="restart_workers")
        ],
        [InlineKeyboardButton("🔁 Restart Admin", callback_data="restart_admin")]
    ])
# ===========================================

# ================= COMMANDS =================
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Admin Panel Ready",
        reply_markup=main_panel()
    )

@admin_only
async def alias_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3 or args[0] != "add":
        await update.message.reply_text("Usage:\n/alias add name @channel_or_id")
        return
    _, name, channel = args
    if not valid_channel(channel):
        await update.message.reply_text("❌ Invalid channel")
        return
    data = load_aliases()
    data[name] = channel
    save_aliases(data)
    await update.message.reply_text(f"✅ Alias saved: {name} → {channel}")
# ============================================

# ================= BUTTON HANDLER ===========
@admin_only
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # ---------- WORKERS ----------
    if q.data == "start_workers":
        run("sudo systemctl start telegram_worker@1 telegram_worker@2 || true")
        await q.edit_message_text("▶ Workers started", reply_markup=main_panel())

    elif q.data == "restart_workers":
        run("sudo systemctl restart telegram_worker@1 telegram_worker@2 || true")
        await q.edit_message_text("♻ Workers restarted", reply_markup=main_panel())

    elif q.data == "restart_admin":
        subprocess.Popen(["sudo", "systemctl", "restart", "telegram_admin"])

    # ---------- CREATE JOB ----------
    elif q.data == "create_job":
        JOB_WIZARD[q.from_user.id] = {"step": 1}
        await q.edit_message_text(
            "🧙 Job Wizard\n\nStep 1️⃣\nSend SOURCE channel / group / ID / alias"
        )

    # ---------- DASHBOARD ----------
    elif q.data == "dashboard":
        text = "📊 Jobs\n\n"
        kb = []

        for pr in ["high", "normal", "low"]:
            folder = os.path.join(JOBS_DIR, pr)
            if not os.path.isdir(folder):
                continue
            for f in os.listdir(folder):
                if not f.endswith(".json"):
                    continue
                job = json.load(open(os.path.join(folder, f)))
                text += f"🆔 {job['id']} | {job.get('progress',0)}% | {job['status']}\n"
                kb.append([
                    InlineKeyboardButton(
                        f"🔍 View {job['id']}",
                        callback_data=f"view:{pr}:{f}"
                    )
                ])

        kb.append([InlineKeyboardButton("⬅ Back", callback_data="back")])
        await q.edit_message_text(text or "No jobs", reply_markup=InlineKeyboardMarkup(kb))

    elif q.data == "back":
        await q.edit_message_text("⬅ Back", reply_markup=main_panel())

    # ---------- VIEW JOB ----------
    elif q.data.startswith("view:"):
        _, pr, fn = q.data.split(":")
        path = os.path.join(JOBS_DIR, pr, fn)
        job = json.load(open(path))

        p = job.get("progress", 0)
        text = (
            f"🆔 {job['id']}\n"
            f"{progress_bar(p)} {p}%\n\n"
            f"📦 {job.get('processed_items',0)} / {job.get('batch_size',0)}\n"
            f"⚡ {job.get('speed',0)} msg/s\n"
            f"⏱ ETA: {fmt_eta(job.get('eta_seconds'))}\n"
            f"📨 Batch: {job.get('batch_size')}\n"
            f"⚙ Status: {job['status']}\n"
            f"❌ Reason: {job.get('failed_reason','-')}"
        )

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▶ Start", callback_data=f"start:{pr}:{fn}"),
                InlineKeyboardButton("⏸ Pause", callback_data=f"pause:{pr}:{fn}")
            ],
            [
                InlineKeyboardButton("▶ Resume", callback_data=f"resume:{pr}:{fn}"),
                InlineKeyboardButton("🔄 Retry", callback_data=f"retry:{pr}:{fn}")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"view:{pr}:{fn}")
            ],
            [
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete:{pr}:{fn}")
            ],
            [InlineKeyboardButton("⬅ Back", callback_data="dashboard")]
        ])

        await q.edit_message_text(text, reply_markup=kb)

    # ---------- JOB ACTIONS ----------
    elif q.data.startswith(("pause","resume","retry","start")):
        act, pr, fn = q.data.split(":")
        path = os.path.join(JOBS_DIR, pr, fn)
        job = json.load(open(path))

        if act == "pause":
            job["status"] = "paused"
        elif act in ("resume","start"):
            job["status"] = "running"
        elif act == "retry":
            job["status"] = "running"
            job["retry_count"] = 0

        json.dump(job, open(path,"w"), indent=2)
        await q.answer(f"✅ {act.capitalize()} done")

    elif q.data.startswith("delete:"):
        _, pr, fn = q.data.split(":")
        os.remove(os.path.join(JOBS_DIR, pr, fn))
        await q.answer("🗑 Job deleted")

    elif q.data == "confirm_job":
        await confirm_job(update, context)
# ============================================

# ================= WIZARD TEXT HANDLER =======
@admin_only
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in JOB_WIZARD:
        return

    wiz = JOB_WIZARD[uid]
    msg = resolve_alias(update.message.text.strip())

    if wiz["step"] == 1:
        if not valid_channel(msg):
            await update.message.reply_text("❌ Invalid source")
            return
        wiz["source"] = msg
        wiz["step"] = 2
        await update.message.reply_text("Step 2️⃣ Send TARGET")

    elif wiz["step"] == 2:
        if not valid_channel(msg) or msg == wiz["source"]:
            await update.message.reply_text("❌ Invalid target")
            return
        wiz["target"] = msg
        wiz["step"] = 3
        await update.message.reply_text("Step 3️⃣ Priority (high/normal/low)")

    elif wiz["step"] == 3:
        if msg not in ("high","normal","low"):
            await update.message.reply_text("❌ Invalid priority")
            return
        wiz["priority"] = msg
        wiz["step"] = 4
        await update.message.reply_text("Step 4️⃣ Batch size")

    elif wiz["step"] == 4:
        if not msg.isdigit():
            await update.message.reply_text("❌ Invalid batch size")
            return

        wiz["batch_size"] = int(msg)

        text = (
            "🔍 Job Preview\n\n"
            f"Source: {wiz['source']}\n"
            f"Target: {wiz['target']}\n"
            f"Priority: {wiz['priority']}\n"
            f"Batch: {wiz['batch_size']}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_job"),
             InlineKeyboardButton("❌ Cancel", callback_data="back")]
        ])

        await update.message.reply_text(text, reply_markup=kb)
# ============================================

# ================= CONFIRM JOB ===============
@admin_only
async def confirm_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    wiz = JOB_WIZARD.pop(uid, None)
    if not wiz:
        await q.edit_message_text("❌ No job to confirm", reply_markup=main_panel())
        return

    pr = wiz["priority"]
    os.makedirs(os.path.join(JOBS_DIR, pr), exist_ok=True)

    job_id = f"job_{uuid.uuid4().hex[:6]}"
    fn = f"{job_id}.json"
    path = os.path.join(JOBS_DIR, pr, fn)

    job = {
        "id": job_id,
        "source": wiz["source"],
        "target": wiz["target"],
        "priority": pr,
        "status": "running",
        "batch_size": wiz["batch_size"],
        "processed_items": 0,
        "last_message_id": 0,
        "progress": 0,
        "speed": 0,
        "eta_seconds": 0,
        "retry_count": 0,
        "failed_reason": "",
        "created_at": int(time.time())
    }

    json.dump(job, open(path, "w"), indent=2)

    # AUTO OPEN DETAIL VIEW
    await buttons(update, context)
# ============================================

# ================= MAIN =====================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("alias", alias_cmd))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("✅ Admin bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
# =================================================
