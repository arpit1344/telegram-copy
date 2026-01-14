# admin_bot.py
# SIMPLE & STABLE ADMIN PANEL
# - Auto-detect single / multi worker
# - No @1 confusion
# - Restart / Start / Stop works safely

import os
import subprocess
import time
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ========= CONFIG =========

BOT_TOKEN = "8536928293:AAHUTdOtkWad8QxsZHoTxslXm9tcIFbbeis"
ADMIN_ID = 8214011603

# ==========================


# ========= HELPERS =========

def run(cmd):
    return subprocess.getoutput(cmd)

def worker_units():
    """
    Auto-detect workers.
    If telegram_worker@1 exists → multi-worker
    Else → single worker
    """
    out = run("systemctl list-unit-files | grep telegram_worker@")
    if "telegram_worker@" in out:
        return ["telegram_worker@1", "telegram_worker@2"]
    else:
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


# ========= SECURITY =========

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
        return await func(update, context)
    return wrapper


# ========= UI =========

def panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Workers", callback_data="start")],
        [InlineKeyboardButton("⏹ Stop Workers", callback_data="stop")],
        [InlineKeyboardButton("♻️ Restart Workers", callback_data="restart")],
        [InlineKeyboardButton("🔁 Restart Admin Bot", callback_data="restart_admin")],
    ])


# ========= HANDLERS =========

@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Admin Panel Ready",
        reply_markup=panel()
    )


@admin_only
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "start":
        start_workers()
        await q.answer("▶️ Workers started")

    elif q.data == "stop":
        stop_workers()
        await q.answer("⏹ Workers stopped")

    elif q.data == "restart":
        restart_workers()
        await q.answer("♻️ Workers restarted")

    elif q.data == "restart_admin":
        await q.answer("🔁 Restarting admin bot…")
        subprocess.Popen(["sudo", "systemctl", "restart", "telegram_admin"])


# ========= MAIN =========

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("✅ Admin Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()
