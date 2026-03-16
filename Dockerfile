# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# ── Set working directory ─────────────────────────────────────────────────────
WORKDIR /app

# ── Install dependencies first (layer-cache friendly) ─────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy bot source ───────────────────────────────────────────────────────────
COPY bot.py .

# ── Run the bot ───────────────────────────────────────────────────────────────
CMD ["python", "bot.py"]
