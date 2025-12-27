import os
import requests
import logging
import re
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home(): return "YouTube API Bot Fix Active", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "social-media-video-downloader.p.rapidapi.com"
API_URL = "https://social-media-video-downloader.p.rapidapi.com/youtube/v3/video/details"

def get_video_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'youtu\.be\/([0-9A-Za-z_-]{11})']
    for p in patterns:
        match = re.search(p, url)
        if match: return match.group(1)
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    video_id = get_video_id(url)
    
    if not video_id:
        await update.message.reply_text("❌ Надішліть коректне посилання на YouTube.")
        return

    status_msg = await update.message.reply_text("🔍 Аналізую потоки відео...")

    params = {
        "videoId": video_id,
        "renderableFormats": "720p,1080p",
        "urlAccess": "proxied",
        "getTranscript": "false"
    }

    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": RAPID_API_HOST
    }

    try:
        response = requests.get(API_URL, headers=headers, params=params, timeout=30)
        data = response.json()
        
        # ГЛИБОКИЙ ПОШУК ПОСИЛАННЯ
        video_url = None
        
        # Варіант 1: У масиві formats
        formats = data.get("formats", [])
        if not formats and "adaptiveFormats" in data: # Деякі API ділять на адаптивні
            formats = data.get("adaptiveFormats", [])

        for f in formats:
            # Шукаємо прямий URL або посилання з підписом
            if f.get("url"):
                video_url = f.get("url")
                break
            elif f.get("signatureCipher"):
                # Якщо відео зашифроване, це API має саме його розшифрувати
                logger.info("Знайдено зашифрований потік")

        # Варіант 2: Якщо API повертає посилання в іншому полі
        if not video_url:
            video_url = data.get("downloadUrl") or data.get("link")

        if video_url:
            try:
                await update.message.reply_video(video=video_url, caption="✅ Завантажено!")
                await status_msg.delete()
            except Exception as e:
                # Якщо посилання є, але Telegram не може його "проковтнути" (HTTP 403 або розмір)
                await status_msg.edit_text(f"✅ Посилання знайдено, але Telegram не зміг отримати доступ до файлу.\n\n🔗 [Завантажити напряму]({video_url})", parse_mode='Markdown')
        else:
            # Виводимо помилку з відповіді API, якщо вона там є
            error_detail = data.get("message") or "Посилання відсутнє у відповіді API."
            await status_msg.edit_text(f"❌ Не вдалося отримати відео: {error_detail}")
            logger.error(f"Full API response for debug: {data}")

    except Exception as e:
        await status_msg.edit_text(f"⚠️ Помилка мережі: {str(e)[:50]}")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
