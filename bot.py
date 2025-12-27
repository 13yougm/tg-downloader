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
def home(): return "Cobalt RapidAPI Bot is Live", 200
def run_flask(): 
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# Налаштування з твого cURL
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "cobalt-social-media-downloader.p.rapidapi.com"
API_URL = "https://cobalt-social-media-downloader.p.rapidapi.com/"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or not url.startswith("http"): return
    
    status_msg = await update.message.reply_text("⏳ Cobalt обробляє посилання...")

    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPID_API_HOST,
        "x-rapidapi-key": RAPID_API_KEY
    }
    
    # Тіло запиту згідно з документацією Cobalt на RapidAPI
    payload = {
        "url": url,
        "videoQuality": "720", # Оптимально для Telegram
        "filenameStyle": "basic",
        "downloadMode": "auto"
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=40)
        data = response.json()
        logger.info(f"API Response: {data}")

        # Стандартні статуси Cobalt: 'stream', 'redirect', 'tunnel', 'picker'
        status = data.get("status")

        if status in ["stream", "redirect", "tunnel"]:
            video_url = data.get("url")
            if video_url:
                try:
                    await update.message.reply_video(video=video_url, caption="✅ Завантажено успішно!")
                    await status_msg.delete()
                except Exception:
                    await status_msg.edit_text(f"✅ Готово, але файл надіслано посиланням:\n\n🔗 [Завантажити]({video_url})", parse_mode='Markdown')
            else:
                await status_msg.edit_text("❌ Помилка: API не надало посилання.")

        elif status == "picker":
            # Якщо це слайдшоу (TikTok/Instagram)
            picker = data.get("picker", [])
            first_item = picker[0].get("url") if picker else None
            if first_item:
                await update.message.reply_photo(photo=first_item, caption="Це фото-пост. ✅")
            await status_msg.delete()

        elif status == "error":
            error_text = data.get("text", "Unknown Cobalt error")
            await status_msg.edit_text(f"❌ Помилка Cobalt: {error_text}")
        
        else:
            await status_msg.edit_text("⚠️ Неочікувана відповідь від сервера.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"⚠️ Помилка з'єднання з API.")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    if TOKEN:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()
