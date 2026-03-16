import os
import io
import zipfile
import logging
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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g., "https://yourdomain.com"
PORT = int(os.environ.get("PORT", 8443))

# user_sessions[user_id] = {
#   "mode": "text" | "zip",
#   "texts": [...],
#   "files": [{"name": ..., "data": bytes}],
#   "awaiting_filename": bool,
# }
user_sessions = {}


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)

    keyboard = [
        [
            InlineKeyboardButton("📝  Text → TXT File", callback_data="mode_text"),
            InlineKeyboardButton("🗜️  ZIP Maker",        callback_data="mode_zip"),
        ]
    ]
    await update.message.reply_text(
        "👋 *Welcome to the 2-in-1 Bot!*\n\n"
        "Please choose a mode to get started:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ── Mode selection ────────────────────────────────────────────────────────────

async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "mode_text":
        user_sessions[user_id] = {"mode": "text", "texts": []}
        await query.edit_message_text(
            "📝 *Text → TXT File Mode*\n\n"
            "Send me your text messages one by one.\n"
            "When you're done, send /done and I'll package everything into a `.txt` file!",
            parse_mode="Markdown",
        )

    elif query.data == "mode_zip":
        user_sessions[user_id] = {"mode": "zip", "files": []}
        await query.edit_message_text(
            "🗜️ *ZIP Maker Mode*\n\n"
            "Send me the files you want to zip (documents, photos, audio, video, etc.).\n"
            "When you're done, send /done and I'll bundle them into a `.zip` archive!",
            parse_mode="Markdown",
        )


# ── Restart callback ──────────────────────────────────────────────────────────

async def restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_sessions.pop(query.from_user.id, None)

    keyboard = [
        [
            InlineKeyboardButton("📝  Text → TXT File", callback_data="mode_text"),
            InlineKeyboardButton("🗜️  ZIP Maker",        callback_data="mode_zip"),
        ]
    ]
    await query.edit_message_text(
        "👋 *Welcome back!*\n\nChoose a mode to get started:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ── /done ─────────────────────────────────────────────────────────────────────

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session:
        await update.message.reply_text(
            "⚠️ No active session. Send /start to begin!"
        )
        return

    # Check if we have content
    mode = session["mode"]
    if mode == "text" and not session.get("texts"):
        await update.message.reply_text(
            "⚠️ You haven't sent any text yet! Send some messages first, then /done."
        )
        return
    elif mode == "zip" and not session.get("files"):
        await update.message.reply_text(
            "⚠️ You haven't sent any files yet! Send some files first, then /done."
        )
        return

    # Ask for custom filename
    session["awaiting_filename"] = True
    await update.message.reply_text(
        "📝 *Please send me the desired filename* (without extension)\n"
        "or type /skip to use the default name.\n"
        "_(e.g., `my_notes` for a text file, `my_archive` for a zip)_",
        parse_mode="Markdown",
    )


# ── /skip ─────────────────────────────────────────────────────────────────────

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session or not session.get("awaiting_filename"):
        await update.message.reply_text("⚠️ No filename request pending. Use /done first.")
        return

    # Generate file with default name
    await generate_and_send_file(update, context, custom_name=None)


# ── Helper to generate and send the final file ─────────────────────────────────

async def generate_and_send_file(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_name: str | None):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    if not session:
        return

    mode = session["mode"]

    try:
        if mode == "text":
            texts = session["texts"]
            combined = "\n\n".join(texts)
            buf = io.BytesIO(combined.encode("utf-8"))

            # Determine filename
            if custom_name:
                # Sanitize and add .txt if needed
                custom_name = os.path.basename(custom_name).strip(". ")
                if not custom_name:
                    custom_name = "output"
                if not custom_name.lower().endswith(".txt"):
                    filename = custom_name + ".txt"
                else:
                    filename = custom_name
            else:
                filename = "output.txt"

            buf.name = filename
            await update.message.reply_document(
                document=buf,
                filename=filename,
                caption=f"✅ Here's your TXT file containing *{len(texts)} message(s)*!",
                parse_mode="Markdown",
            )

        elif mode == "zip":
            files = session["files"]
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.writestr(f["name"], f["data"])
            zip_buf.seek(0)

            if custom_name:
                custom_name = os.path.basename(custom_name).strip(". ")
                if not custom_name:
                    custom_name = "archive"
                if not custom_name.lower().endswith(".zip"):
                    filename = custom_name + ".zip"
                else:
                    filename = custom_name
            else:
                filename = "archive.zip"

            zip_buf.name = filename
            await update.message.reply_document(
                document=zip_buf,
                filename=filename,
                caption=f"✅ Here's your ZIP archive containing *{len(files)} file(s)*!",
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"Error generating file: {e}")
        await update.message.reply_text("❌ An error occurred while creating your file.")
        return

    # Clear session after successful send
    user_sessions.pop(user_id, None)

    # Offer restart
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

    # If we're waiting for a filename, treat this message as the custom name
    if session.get("awaiting_filename"):
        custom_name = update.message.text.strip()
        # Sanitize a bit
        if not custom_name:
            await update.message.reply_text("⚠️ Filename cannot be empty. Please try again or use /skip.")
            return
        # Remove any path separators
        custom_name = os.path.basename(custom_name)
        # Remove leading/trailing dots and spaces
        custom_name = custom_name.strip(". ")
        if not custom_name:
            await update.message.reply_text("⚠️ Invalid filename. Please try again or use /skip.")
            return

        # Generate file with this custom name
        await generate_and_send_file(update, context, custom_name=custom_name)
        return

    # Normal text collection
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

    # If we're waiting for a filename, reject files with a reminder
    if session.get("awaiting_filename"):
        await update.message.reply_text(
            "⚠️ I'm waiting for a filename from you. Please send the desired filename as text, "
            "or type /skip to use the default name."
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
        tg_file = await msg.document.get_file()
        filename = msg.document.file_name or f"file_{len(session['files']) + 1}"
    elif msg.photo:
        tg_file = await msg.photo[-1].get_file()
        filename = f"photo_{len(session['files']) + 1}.jpg"
    elif msg.audio:
        tg_file = await msg.audio.get_file()
        filename = msg.audio.file_name or f"audio_{len(session['files']) + 1}.mp3"
    elif msg.video:
        tg_file = await msg.video.get_file()
        filename = msg.video.file_name or f"video_{len(session['files']) + 1}.mp4"
    elif msg.voice:
        tg_file = await msg.voice.get_file()
        filename = f"voice_{len(session['files']) + 1}.ogg"
    elif msg.sticker:
        tg_file = await msg.sticker.get_file()
        filename = f"sticker_{len(session['files']) + 1}.webp"
    else:
        await update.message.reply_text("⚠️ Unsupported file type.")
        return

    # Deduplicate filename inside zip
    existing = [f["name"] for f in session["files"]]
    base_name = filename
    counter = 1
    while filename in existing:
        if "." in base_name:
            name, ext = base_name.rsplit(".", 1)
            filename = f"{name}_{counter}.{ext}"
        else:
            filename = f"{base_name}_{counter}"
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
        "• /done   — Finish and choose a custom filename\n"
        "• /skip   — Skip custom naming and use default name\n"
        "• /cancel — Cancel current session\n"
        "• /help   — Show this message\n\n"
        "*Modes:*\n"
        "📝 *Text → TXT* — Collect text messages → get a `.txt` file\n"
        "🗜️ *ZIP Maker*   — Collect files → get a `.zip` archive",
        parse_mode="Markdown",
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("done",    done))
    app.add_handler(CommandHandler("skip",    skip))
    app.add_handler(CommandHandler("cancel",  cancel))
    app.add_handler(CommandHandler("help",    help_command))

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

    # Start webhook
    if WEBHOOK_URL:
        logger.info(f"Starting webhook on port {PORT} with URL {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        # Fallback to polling if WEBHOOK_URL is not set (for local testing)
        logger.warning("WEBHOOK_URL not set, falling back to polling.")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
