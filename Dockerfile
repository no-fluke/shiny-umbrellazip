FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# Force no cache so the correct package is always installed
RUN pip install --no-cache-dir "python-telegram-bot[webhooks]==21.6"

COPY bot.py .

EXPOSE 8080

CMD ["python", "bot.py"]
