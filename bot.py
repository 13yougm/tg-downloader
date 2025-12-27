import os
import requests
import logging
import re
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask для Koyeb
app = Flask('')
@app.route('/')
def home(): return "YouTube Downloader API Active", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# Налаштування нового API (social-media-video-downloader)
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "social-media-video-downloader.p.rapidapi.com"
API_URL = "https://social-media-video-downloader.p.rapidapi.com/youtube/v3/video/details"

def extract_video_id(url):
    """Витягує ID відео з посилання YouTube"""
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ Це API спеціалізується на YouTube. Будь ласка, надішліть посилання на YouTube.")
        return
    
    video_id = extract_video_id(url)
    if not video_id:
        await update.message.reply_text("❌ не вдалося знайти ID відео у посиланні.")
        return

    status_msg = await update.message.reply_text("🔍 Отримую дані відео з YouTube...")

    # Параметри згідно з твоїм cURL
    querystring = {
        "videoId": video_id,
        "renderableFormats": "720p,1080p",
        "urlAccess": "proxied", # Використовуємо проксі для обходу блокувань
        "getTranscript": "false"
    }

    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": RAPID_API_HOST
    }

    try:
        response = requests.get(API_URL, headers=headers, params=querystring, timeout=30)
        data = response.json()
        logger.info(f"API Response: {data}")

        # Розбір структури відповіді (згідно з YouTube Details API)
        # Зазвичай посилання знаходяться у відео-форматах
        formats = data.get("formats", [])
        video_url = None

        # Шукаємо найкращий формат з прямим посиланням
        for f in formats:
            if f.get("url"):
                video_url = f.get("url")
                break

        if video_url:
            try:
                await update.message.reply_video(video=video_url, caption="✅ YouTube відео завантажено!")
                await status_msg.delete()
            except Exception:
                await status_msg.edit_text(f"✅ Відео знайдено!\n\n🔗 [Завантажити файл]({video_url})", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ Не вдалося отримати посилання. Можливо, відео обмежене або приватне.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("⚠️ Помилка звернення до API завантажувача.")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    if TOKEN:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()
