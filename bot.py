import os
import io
import zipfile
import logging
import re
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
#   "mode": "text" | "zip" | "convert",
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
            InlineKeyboardButton("📄  Convert to GS Format", callback_data="mode_convert"),
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

    elif query.data == "mode_convert":
        user_sessions[user_id] = {"mode": "convert"}
        await query.edit_message_text(
            "📄 *Convert to GS Format Mode*\n\n"
            "Send me a `.txt` file containing questions in the **annotated format** "
            "(with Q.No:, options, Correct option:, and Explanation).\n\n"
            "I will restructure it into the GS format (like `Chslgs3(4).txt`), "
            "filling in the correct option and explanation automatically.",
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
            InlineKeyboardButton("📄  Convert to GS Format", callback_data="mode_convert"),
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
    elif mode == "convert":
        await update.message.reply_text(
            "⚠️ In Convert mode, the file is processed as soon as you upload it.\n"
            "You don't need to use /done here."
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

        # Convert mode does not go through this function
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


# ── New conversion function for annotated format ───────────────────────────────

def convert_annotated_to_gs(text: str) -> str:
    """
    Convert a text file containing questions with Q.No:, options, Correct option:, and Explanation
    into the GS format with filled-in correct option and explanation.
    """
    lines = text.splitlines()
    output_blocks = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()
        # Detect start of a question: "Q.No:" possibly surrounded by ** or other markdown
        if re.match(r'\**Q\.No\s*:\s*\d+\**', line, re.IGNORECASE):
            # Extract question number
            match_num = re.search(r'Q\.No\s*:\s*(\d+)', line, re.IGNORECASE)
            if not match_num:
                i += 1
                continue
            q_num = match_num.group(1)

            # Skip the Q.No line
            i += 1

            # Collect question text (may span several lines until we hit an option line or "Correct option:")
            question_lines = []
            while i < n:
                line = lines[i].strip()
                # Stop if we hit an option line (A., B., etc.) or the correct option header
                if (re.match(r'^[A-D][\.\)]', line, re.IGNORECASE) or
                    re.match(r'\**Correct option:', line, re.IGNORECASE)):
                    break
                # Also stop if we hit another Q.No (in case of missing blank lines)
                if re.match(r'\**Q\.No\s*:', line, re.IGNORECASE):
                    break
                # Collect non-empty lines, but ignore empty lines that separate content
                if line:
                    question_lines.append(line)
                i += 1

            question_text = " ".join(question_lines).strip()

            # Collect options (A, B, C, D)
            options = {}
            # We'll look for lines starting with A., B., C., D. (case-insensitive)
            # We'll collect them in the order they appear, but store in dict
            # We'll also handle cases where the option text continues on the next line (e.g., after a line break)
            # For simplicity, assume each option is on its own line (the input format usually is like that)
            while i < n:
                line = lines[i].strip()
                match_opt = re.match(r'^([A-D])[\.\)]\s*(.*)', line, re.IGNORECASE)
                if not match_opt:
                    break
                opt_letter = match_opt.group(1).upper()
                opt_text = match_opt.group(2).strip()
                options[opt_letter] = opt_text
                i += 1

            # Now we expect a line with "Correct option:" (maybe with **)
            correct_option_letter = None
            while i < n:
                line = lines[i].strip()
                if re.match(r'\**Correct option:', line, re.IGNORECASE):
                    # Extract the option letter (e.g., "B", "B.", "B. were going on")
                    # We'll take the first capital letter after the colon, ignoring spaces and punctuation
                    after_colon = re.sub(r'^.*?:', '', line, flags=re.IGNORECASE).strip()
                    # Find first letter that is A, B, C, D (case-insensitive)
                    match_letter = re.search(r'([A-D])', after_colon, re.IGNORECASE)
                    if match_letter:
                        correct_option_letter = match_letter.group(1).lower()
                    i += 1
                    break
                i += 1

            # If we didn't find a correct option, set to empty string
            if not correct_option_letter:
                correct_option_letter = ""

            # Now we expect the explanation header: "Explanation (in depth and detailed):"
            explanation_lines = []
            while i < n:
                line = lines[i].strip()
                if re.match(r'\**Explanation\s*\(.*\)\s*:', line, re.IGNORECASE):
                    # This line may contain the start of the explanation after the colon
                    # Extract text after colon if any
                    after_colon = re.sub(r'^.*?:', '', line, flags=re.IGNORECASE).strip()
                    if after_colon:
                        explanation_lines.append(after_colon)
                    i += 1
                    # Now collect all subsequent lines until we hit the next question or end of file
                    while i < n:
                        next_line = lines[i].strip()
                        # Stop if we encounter a new Q.No line
                        if re.match(r'\**Q\.No\s*:', next_line, re.IGNORECASE):
                            break
                        # Also stop if we encounter a new Correct option (should not happen, but just in case)
                        if re.match(r'\**Correct option:', next_line, re.IGNORECASE):
                            break
                        # Collect explanation text, even if empty lines (they will be collapsed)
                        explanation_lines.append(next_line)
                        i += 1
                    break
                i += 1

            # Combine explanation lines into a single string, removing excessive whitespace
            explanation = " ".join(explanation_lines).strip()

            # Build the output block for this question
            block = f"{q_num}. {question_text}\n"
            block += "    \n"  # blank Hindi question
            for opt in ["A", "B", "C", "D"]:
                opt_en = options.get(opt, "")
                block += f"    {opt.lower()}) {opt_en}\n"
                block += "        \n"  # blank Hindi option
            block += f"Correct option:-{correct_option_letter}\n"
            block += f"ex: {explanation}\n"
            block += "\n"  # blank line between questions

            output_blocks.append(block)

        else:
            i += 1

    return "\n".join(output_blocks).strip()


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
            "⚠️ You're in a mode that expects files or conversion.\n"
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

    mode = session["mode"]

    if mode == "convert":
        # Process the uploaded file as a conversion job
        msg = update.message
        # Only accept documents (text files) for conversion
        if not msg.document:
            await update.message.reply_text(
                "⚠️ Please send a `.txt` document for conversion. Other file types are not supported in this mode."
            )
            return

        # Download the file
        file = await msg.document.get_file()
        file_bytes = io.BytesIO()
        await file.download_to_memory(file_bytes)
        file_bytes.seek(0)
        content = file_bytes.read().decode("utf-8", errors="replace")

        try:
            converted = convert_annotated_to_gs(content)
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            await update.message.reply_text(
                "❌ Failed to convert the file. Please ensure it follows the expected annotated format "
                "(Q.No:, options, Correct option:, Explanation)."
            )
            return

        # Prepare output buffer
        output_buf = io.BytesIO()
        output_buf.write(converted.encode("utf-8"))
        output_buf.seek(0)

        # Determine output filename
        original_name = msg.document.file_name or "converted"
        base, ext = os.path.splitext(original_name)
        if ext.lower() != ".txt":
            output_filename = f"{base}_converted.txt"
        else:
            output_filename = f"{base}_converted{ext}"

        output_buf.name = output_filename

        await update.message.reply_document(
            document=output_buf,
            filename=output_filename,
            caption="✅ Conversion complete! Here's your file in GS format with filled-in correct options and explanations.",
        )

        # Clear session and offer restart
        user_sessions.pop(user_id, None)
        keyboard = [[InlineKeyboardButton("🔄 Start Again", callback_data="restart")]]
        await update.message.reply_text(
            "Want to do something else?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if mode != "zip":
        await update.message.reply_text(
            "⚠️ You're in a mode that does not accept files.\n"
            "Use /start to switch to ZIP Maker or Convert mode.",
            parse_mode="Markdown",
        )
        return

    # ZIP Maker mode: collect files
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
        "• /done   — Finish and choose a custom filename (text/zip modes)\n"
        "• /skip   — Skip custom naming and use default name (text/zip modes)\n"
        "• /cancel — Cancel current session\n"
        "• /help   — Show this message\n\n"
        "*Modes:*\n"
        "📝 *Text → TXT* — Collect text messages → get a `.txt` file\n"
        "🗜️ *ZIP Maker*   — Collect files → get a `.zip` archive\n"
        "📄 *Convert to GS Format* — Upload a `.txt` file with questions, options, correct answer, and explanation → get a properly formatted GS file",
        parse_mode="Markdown",
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

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

    if WEBHOOK_URL:
        logger.info(f"Starting webhook on port {PORT} with URL {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        logger.warning("WEBHOOK_URL not set, falling back to polling.")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
