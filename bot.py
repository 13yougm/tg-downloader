import os
import requests
import logging
import re
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Налаштування логів
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask для стабільної роботи на Koyeb
app = Flask('')
@app.route('/')
def home(): return "YouTube API Bot is Live", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# Дані RapidAPI, які ти надав
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "social-media-video-downloader.p.rapidapi.com"
API_URL = "https://social-media-video-downloader.p.rapidapi.com/youtube/v3/video/details"

def get_video_id(url):
    """Вилучає ID відео з різних типів посилань YouTube (звичайні, shorts, youtu.be)"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', # Звичайні посилання та shorts
        r'youtu\.be\/([0-9A-Za-z_-]{11})',   # Скорочені посилання
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or "http" not in url: return
    
    video_id = get_video_id(url)
    if not video_id:
        await update.message.reply_text("❌ Не вдалося знайти ID відео. Надішліть посилання на YouTube.")
        return

    status_msg = await update.message.reply_text("🔍 Отримую дані з YouTube (через проксі)...")

    # Параметри з твого cURL запиту
    params = {
        "videoId": video_id,
        "renderableFormats": "720p,highres",
        "urlAccess": "proxied", # ОБОВ'ЯЗКОВО для роботи на серверах
        "getTranscript": "false"
    }

    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": RAPID_API_HOST
    }

    try:
        response = requests.get(API_URL, headers=headers, params=params, timeout=30)
        data = response.json()
        logger.info(f"API Response: {data}")

        # Шукаємо посилання у форматах
        video_url = None
        formats = data.get("formats", [])
        
        # Шукаємо перший доступний формат з прямим URL
        if isinstance(formats, list):
            for f in formats:
                if f.get("url"):
                    video_url = f.get("url")
                    break

        if video_url:
            try:
                await update.message.reply_video(video=video_url, caption="✅ Готово!")
                await status_msg.delete()
            except Exception:
                # Якщо Telegram не може завантажити посилання (наприклад, через обмеження розміру)
                await status_msg.edit_text(f"✅ Відео знайдено!\n\n🔗 [Завантажити файл]({video_url})", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ Не вдалося отримати пряме посилання на відео. Можливо, воно обмежене.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("⚠️ Помилка звернення до API.")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    if TOKEN:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()
