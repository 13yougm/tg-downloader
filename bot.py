import os
import requests
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask для Koyeb
app = Flask('')
@app.route('/')
def home(): return "All-In-One API Bot is Live", 200
def run_flask(): 
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# Налаштування з твого нового запиту
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "best-all-in-one-video-downloader1.p.rapidapi.com"
API_URL = "https://best-all-in-one-video-downloader1.p.rapidapi.com/index.php"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or not url.startswith("http"): return
    
    status_msg = await update.message.reply_text("📡 Запит до Best All-In-One API...")

    # ВАЖЛИВО: цей API вимагає x-www-form-urlencoded
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-rapidapi-host": RAPID_API_HOST,
        "x-rapidapi-key": RAPID_API_KEY
    }
    
    # Дані форми (як у звичайному браузері)
    payload = {"url": url}

    try:
        # Використовуємо data= замість json= для формату x-www-form-urlencoded
        response = requests.post(API_URL, data=payload, headers=headers, timeout=30)
        data = response.json()
        logger.info(f"API Response: {data}")

        # Розбір відповіді (цей API часто повертає список відео у полі 'medias' або 'result')
        video_url = None
        
        # Спробуємо знайти посилання в різних можливих полях
        if data.get("medias"):
            video_url = data["medias"][0].get("url")
        elif data.get("url"):
            video_url = data.get("url")
        elif data.get("result") and isinstance(data["result"], list):
            video_url = data["result"][0].get("url")

        if video_url:
            try:
                await update.message.reply_video(video=video_url, caption="✅ Завантажено успішно!")
                await status_msg.delete()
            except Exception:
                await status_msg.edit_text(f"✅ Відео знайдено!\n\n🔗 [Завантажити файл]({video_url})", parse_mode='Markdown')
        else:
            # Якщо API повернуло помилку
            error_msg = data.get("message") or "Посилання не знайдено у відповіді API."
            await status_msg.edit_text(f"❌ Помилка: {error_text}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"⚠️ Помилка з'єднання з API: {str(e)[:50]}")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    if TOKEN:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()
