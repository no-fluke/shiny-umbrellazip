import os
import io
import re
import zipfile
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN   = os.environ.get("BOT_TOKEN",   "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT        = int(os.environ.get("PORT", 8080))

# user_sessions[user_id] = {
#   "mode":        "text" | "zip",
#   "step":        "naming" | "collecting",
#   "output_name": str,          # custom filename WITHOUT extension
#   "texts":       [...],        # text mode only
#   "files":       [{"name": str, "data": bytes}],  # zip mode only
# }
user_sessions = {}

SAFE_NAME = re.compile(r"[^\w\-. ]")


def sanitise(name: str) -> str:
    name = SAFE_NAME.sub("_", name.strip())
    name = name.strip(". ")
    return name if name else None


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_sessions.pop(update.effective_user.id, None)
    keyboard = [[
        InlineKeyboardButton("📝  Text → TXT File", callback_data="mode_text"),
        InlineKeyboardButton("🗜️  ZIP Maker",        callback_data="mode_zip"),
    ]]
    await update.message.reply_text(
        "👋 *Welcome to the 2-in-1 Bot!*\n\nPlease choose a mode to get started:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ── Mode selection ────────────────────────────────────────────────────────────

async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()          # always answer immediately to unfreeze the button
    user_id = query.from_user.id

    try:
        if query.data == "mode_text":
            user_sessions[user_id] = {"mode": "text", "step": "naming", "output_name": "", "texts": []}
            await query.edit_message_text(
                "📝 *Text → TXT File Mode*\n\n"
                "What would you like to name your output file?\n"
                "_(No extension needed — e.g.* `my_notes` *or* `meeting recap`_)\n\n"
                "Send /skip to use the default: `output.txt`",
                parse_mode="Markdown",
            )

        elif query.data == "mode_zip":
            user_sessions[user_id] = {"mode": "zip", "step": "naming", "output_name": "", "files": []}
            await query.edit_message_text(
                "🗜️ *ZIP Maker Mode*\n\n"
                "What would you like to name your ZIP archive?\n"
                "_(No extension needed — e.g.* `project_files` *or* `photos jan`_)\n\n"
                "Send /skip to use the default: `archive.zip`",
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"mode_callback error: {e}\n{traceback.format_exc()}")
        await query.message.reply_text("⚠️ Something went wrong. Please send /start and try again.")


# ── Restart callback ──────────────────────────────────────────────────────────

async def restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()          # always answer immediately to unfreeze the button
    user_sessions.pop(query.from_user.id, None)

    try:
        keyboard = [[
            InlineKeyboardButton("📝  Text → TXT File", callback_data="mode_text"),
            InlineKeyboardButton("🗜️  ZIP Maker",        callback_data="mode_zip"),
        ]]
        await query.edit_message_text(
            "👋 *Welcome back!*\n\nChoose a mode to get started:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"restart_callback error: {e}\n{traceback.format_exc()}")
        await query.message.reply_text("⚠️ Something went wrong. Please send /start and try again.")


# ── /skip ─────────────────────────────────────────────────────────────────────

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session or session.get("step") != "naming":
        await update.message.reply_text("⚠️ Nothing to skip right now.")
        return

    default = "output" if session["mode"] == "text" else "archive"
    session["output_name"] = default
    session["step"] = "collecting"
    await _collecting_prompt(update, session)


# ── /done ─────────────────────────────────────────────────────────────────────

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session:
        await update.message.reply_text("⚠️ No active session. Send /start to begin!")
        return

    if session.get("step") == "naming":
        await update.message.reply_text(
            "⚠️ Please send a filename first, or use /skip to use the default."
        )
        return

    mode     = session["mode"]
    out_base = session.get("output_name") or ("output" if mode == "text" else "archive")

    if mode == "text":
        texts = session.get("texts", [])
        if not texts:
            await update.message.reply_text("⚠️ No messages yet! Send some text first.")
            return

        filename = f"{out_base}.txt"
        buf      = io.BytesIO("\n\n".join(texts).encode("utf-8"))
        buf.name = filename
        await update.message.reply_document(
            document=buf, filename=filename,
            caption=f"✅ Here's *{filename}* — {len(texts)} message(s) inside!",
            parse_mode="Markdown",
        )

    elif mode == "zip":
        files = session.get("files", [])
        if not files:
            await update.message.reply_text("⚠️ No files yet! Send some files first.")
            return

        filename = f"{out_base}.zip"
        zip_buf  = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.writestr(f["name"], f["data"])
        zip_buf.seek(0)
        zip_buf.name = filename
        await update.message.reply_document(
            document=zip_buf, filename=filename,
            caption=f"✅ Here's *{filename}* — {len(files)} file(s) inside!",
            parse_mode="Markdown",
        )

    user_sessions.pop(user_id, None)
    keyboard = [[InlineKeyboardButton("🔄 Start Again", callback_data="restart")]]
    await update.message.reply_text(
        "Want to do something else?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── Incoming text messages ────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session:
        await update.message.reply_text("⚠️ Please send /start first to choose a mode.")
        return

    # Naming step: user provides custom filename
    if session["step"] == "naming":
        clean = sanitise(update.message.text)
        if not clean:
            await update.message.reply_text(
                "⚠️ That name doesn't look valid. Try again or send /skip."
            )
            return
        session["output_name"] = clean
        session["step"]        = "collecting"
        await _collecting_prompt(update, session)
        return

    # Collecting step
    if session["mode"] != "text":
        await update.message.reply_text(
            "⚠️ You're in *ZIP Maker* mode — please send files, not text.\n"
            "Use /start to switch modes.",
            parse_mode="Markdown",
        )
        return

    session["texts"].append(update.message.text.strip())
    count = len(session["texts"])
    await update.message.reply_text(
        f"✅ Message *#{count}* saved! Keep sending or type /done when finished.",
        parse_mode="Markdown",
    )


# ── Incoming files ────────────────────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session:
        await update.message.reply_text("⚠️ Please send /start first to choose a mode.")
        return

    if session["step"] == "naming":
        await update.message.reply_text(
            "⚠️ Please send a filename first (or /skip to use the default)."
        )
        return

    if session["mode"] != "zip":
        await update.message.reply_text(
            "⚠️ You're in *Text → TXT* mode — please send text, not files.\n"
            "Use /start to switch modes.",
            parse_mode="Markdown",
        )
        return

    msg = update.message
    if msg.document:
        tg_file  = await msg.document.get_file()
        filename = msg.document.file_name or f"file_{len(session['files']) + 1}"
    elif msg.photo:
        tg_file  = await msg.photo[-1].get_file()
        filename = f"photo_{len(session['files']) + 1}.jpg"
    elif msg.audio:
        tg_file  = await msg.audio.get_file()
        filename = msg.audio.file_name or f"audio_{len(session['files']) + 1}.mp3"
    elif msg.video:
        tg_file  = await msg.video.get_file()
        filename = msg.video.file_name or f"video_{len(session['files']) + 1}.mp4"
    elif msg.voice:
        tg_file  = await msg.voice.get_file()
        filename = f"voice_{len(session['files']) + 1}.ogg"
    elif msg.sticker:
        tg_file  = await msg.sticker.get_file()
        filename = f"sticker_{len(session['files']) + 1}.webp"
    else:
        await update.message.reply_text("⚠️ Unsupported file type.")
        return

    # Deduplicate filename inside the zip
    existing  = [f["name"] for f in session["files"]]
    base_name = filename
    counter   = 1
    while filename in existing:
        if "." in base_name:
            name, ext = base_name.rsplit(".", 1)
            filename  = f"{name}_{counter}.{ext}"
        else:
            filename  = f"{base_name}_{counter}"
        counter += 1

    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    session["files"].append({"name": filename, "data": buf.getvalue()})

    count = len(session["files"])
    await update.message.reply_text(
        f"✅ *{filename}* added! ({count} file(s) so far)\n"
        "Send more or type /done when finished.",
        parse_mode="Markdown",
    )


# ── /cancel ───────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_sessions:
        user_sessions.pop(user_id)
        await update.message.reply_text("❌ Session cancelled. Send /start to begin again.")
    else:
        await update.message.reply_text("⚠️ No active session. Send /start to begin.")


# ── /help ─────────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *2-in-1 Bot Help*\n\n"
        "*Commands:*\n"
        "• /start  — Choose a mode\n"
        "• /skip   — Use default output filename\n"
        "• /done   — Process & receive your file\n"
        "• /cancel — Cancel current session\n"
        "• /help   — Show this message\n\n"
        "*Modes:*\n"
        "📝 *Text → TXT* — Collect messages → get a named `.txt` file\n"
        "🗜️ *ZIP Maker*   — Collect files    → get a named `.zip` archive",
        parse_mode="Markdown",
    )


# ── Shared helper ─────────────────────────────────────────────────────────────

async def _collecting_prompt(update, session):
    name = session["output_name"]
    ext  = "txt" if session["mode"] == "text" else "zip"
    if session["mode"] == "text":
        body = "Now send me your text messages one by one.\nType /done when finished."
    else:
        body = "Now send me the files you want to zip.\nType /done when finished."
    await update.message.reply_text(
        f"✅ Output will be named *{name}.{ext}*\n\n{body}",
        parse_mode="Markdown",
    )


# ── Global error handler ─────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Unhandled exception: {context.error}\n{traceback.format_exc()}")
    if isinstance(update, Update):
        target = update.effective_message
        if target:
            await target.reply_text("⚠️ An unexpected error occurred. Please send /start to begin again.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("skip",   skip))
    app.add_handler(CommandHandler("done",   done))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help",   help_command))

    app.add_handler(CallbackQueryHandler(mode_callback,    pattern="^mode_"))
    app.add_handler(CallbackQueryHandler(restart_callback, pattern="^restart$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(
        MessageHandler(
            (
                filters.Document.ALL
                | filters.PHOTO
                | filters.AUDIO
                | filters.VIDEO
                | filters.VOICE
                | filters.Sticker.ALL
            ),
            handle_file,
        )
    )

    app.add_error_handler(error_handler)

    if WEBHOOK_URL:
        logger.info(f"✅ Bot starting in WEBHOOK mode on port {PORT}...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}/telegram",
            url_path="telegram",
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("✅ Bot starting in POLLING mode (local dev)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
