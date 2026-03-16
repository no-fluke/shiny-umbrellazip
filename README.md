# 🤖 2-in-1 Telegram Bot

A Telegram bot with two modes:
- **📝 Text → TXT** — Collect text messages and download them as a `.txt` file
- **🗜️ ZIP Maker** — Collect files and download them as a `.zip` archive

---

## 📁 Project Structure

```
telegram-bot/
├── bot.py            # Main bot logic
├── requirements.txt  # Python dependencies
├── render.yaml       # Render deployment config
└── README.md
```

---

## 🚀 Setup & Deployment

### Step 1 — Create your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **Bot Token** you receive (looks like `123456789:ABCDefgh...`)

---

### Step 2 — Deploy to Render

1. Push this project to a **GitHub repository**

2. Go to [render.com](https://render.com) and log in

3. Click **"New +"** → **"Background Worker"**

4. Connect your GitHub repo

5. Render will auto-detect `render.yaml`. Confirm these settings:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`

6. Under **Environment Variables**, add:
   | Key         | Value                          |
   |-------------|--------------------------------|
   | `BOT_TOKEN` | Your bot token from BotFather  |

7. Click **"Create Background Worker"** — Render will build and start the bot!

---

### Step 3 — Set Bot Commands (Optional but recommended)

In BotFather, send `/setcommands` and paste:

```
start - Choose a mode
done - Process & receive your file
cancel - Cancel current session
help - Show help message
```

---

## 💬 How to Use the Bot

| Step | What to do |
|------|-----------|
| 1 | Send `/start` |
| 2 | Choose **📝 Text → TXT** or **🗜️ ZIP Maker** |
| 3 | Send your messages / files |
| 4 | Send `/done` when finished |
| 5 | Receive your `.txt` or `.zip` file! |

---

## 📦 Supported File Types (ZIP mode)

- Documents (PDF, DOCX, XLSX, etc.)
- Photos (JPG, PNG, etc.)
- Audio files (MP3, etc.)
- Video files (MP4, etc.)
- Voice messages (OGG)
- Stickers (WEBP)

---

## ⚠️ Notes

- Sessions are stored **in memory** — restarting the bot clears all active sessions
- Telegram's max file upload size is **20 MB per file** for bots
- The bot uses **polling** (not webhooks) — ideal for Render's free Background Worker tier
