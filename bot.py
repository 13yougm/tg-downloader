import os
import requests
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Логування для відстеження помилок у Koyeb
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home(): return "API Bot is Live", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# Дані твого останнього знайденого API
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "best-all-in-one-video-downloader1.p.rapidapi.com"
API_URL = "https://best-all-in-one-video-downloader1.p.rapidapi.com/index.php"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or not url.startswith("http"): return
    
    status_msg = await update.message.reply_text("📡 З'єднуюсь із сервером завантаження...")

    # ВАЖЛИВО: Використовуємо заголовки саме для form-data
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "x-rapidapi-host": RAPID_API_HOST,
        "x-rapidapi-key": RAPID_API_KEY
    }
    
    # Дані відправляються як звичайна форма
    payload = {"url": url}

    try:
        # data= відправляє як x-www-form-urlencoded (те, що потрібно для index.php)
        response = requests.post(API_URL, data=payload, headers=headers, timeout=30)
        
        # Перевірка на успішний статус HTTP
        if response.status_code != 200:
            await status_msg.edit_text(f"❌ Сервер API повернув помилку {response.status_code}")
            return

        data = response.json()
        logger.info(f"API Response: {data}")

        # Пошук відео посилання (у цього API структура може бути різною)
        video_url = None
        
        # Перевіряємо різні варіанти, де може лежати лінк
        if data.get("medias"):
            video_url = data["medias"][0].get("url")
        elif data.get("url"):
            video_url = data.get("url")
        elif data.get("result"):
            res = data.get("result")
            video_url = res[0].get("url") if isinstance(res, list) else res.get("url")

        if video_url:
            try:
                await update.message.reply_video(video=video_url, caption="✅ Успішно завантажено!")
                await status_msg.delete()
            except Exception:
                # Якщо Telegram не зміг завантажити (файл > 50MB або блок по IP)
                await status_msg.edit_text(f"🔗 Відео знайдено! Натисніть для завантаження:\n\n[ЗАВАНТАЖИТИ]({video_url})", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ API не змогло знайти відео за цим посиланням. Можливо, воно приватне.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"⚠️ Технічна помилка: {str(e)[:50]}")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    if TOKEN:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()
