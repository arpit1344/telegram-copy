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
ALIAS_FILE = "channel_aliases.json"
# ================================

JOB_WIZARD = {}

# -------- UTIL --------
def run(cmd):
    return subprocess.getoutput(cmd)

def load_aliases():
    if not os.path.exists(ALIAS_FILE):
        return {}
    return json.load(open(ALIAS_FILE))

def save_aliases(data):
    json.dump(data, open(ALIAS_FILE, "w"), indent=2)

def resolve_alias(inp):
    return load_aliases().get(inp, inp)

def valid_channel(inp: str) -> bool:
    if inp.startswith("@") and len(inp) > 1:
        return True
    if inp.startswith("-100") and inp[4:].isdigit():
        return True
    return False

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
        [InlineKeyboardButton("♻ Restart Workers", callback_data="restart_workers")],
    ])

# -------- COMMANDS --------
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Admin Panel Ready", reply_markup=main_panel())

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

# -------- BUTTON HANDLER --------
@admin_only
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "create_job":
        JOB_WIZARD[q.from_user.id] = {"step": 1}
        await q.edit_message_text(
            "🧙‍♂️ Job Wizard\n\nStep 1️⃣\nSend SOURCE (channel/group/ID/alias)"
        )

    elif q.data == "confirm_job":
        wiz = JOB_WIZARD.get(q.from_user.id)
        if not wiz:
            return

        pr = wiz["priority"]
        os.makedirs(f"jobs/{pr}", exist_ok=True)

        job = {
            "id": f"job_{uuid.uuid4().hex[:6]}",
            "source": wiz["source"],
            "target": wiz["target"],
            "priority": pr,
            "status": "running",
            "batch_size": wiz["batch_size"],
            "processed_items": 0,
            "total_items": 0,
            "progress": 0,
            "last_message_id": 0,
            "retry_count": 0,
            "max_retries": 3,
            "created_at": int(time.time()),
        }

        json.dump(job, open(f"jobs/{pr}/{job['id']}.json", "w"), indent=2)
        JOB_WIZARD.pop(q.from_user.id, None)
        await q.edit_message_text("✅ Job created!", reply_markup=main_panel())

# -------- TEXT HANDLER (Wizard) --------
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
        await update.message.reply_text("Step 2️⃣\nSend TARGET")

    elif wiz["step"] == 2:
        if not valid_channel(msg) or msg == wiz["source"]:
            await update.message.reply_text("❌ Invalid target")
            return
        wiz["target"] = msg
        wiz["step"] = 3
        await update.message.reply_text("Step 3️⃣\nPriority: high / normal / low")

    elif wiz["step"] == 3:
        if msg not in ("high", "normal", "low"):
            await update.message.reply_text("❌ Invalid priority")
            return
        wiz["priority"] = msg
        wiz["step"] = 4
        await update.message.reply_text("Step 4️⃣\nBatch size (number)")

    elif wiz["step"] == 4:
        if not msg.isdigit() or int(msg) <= 0:
            await update.message.reply_text("❌ Invalid batch size")
            return

        wiz["batch_size"] = int(msg)
        wiz["step"] = 5

        text = (
            "🔍 Job Preview\n\n"
            f"Source: {wiz['source']}\n"
            f"Target: {wiz['target']}\n"
            f"Priority: {wiz['priority']}\n"
            f"Batch size: {wiz['batch_size']}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_job"),
             InlineKeyboardButton("❌ Cancel", callback_data="back")]
        ])

        await update.message.reply_text(text, reply_markup=kb)

# -------- MAIN --------
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
