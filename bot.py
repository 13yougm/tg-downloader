import os
import requests
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Flask для Koyeb (щоб сервіс був Healthy)
app = Flask('')
@app.route('/')
def home(): return "API Bot is Live", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# Дані з твого запиту
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "social-download-all-in-one.p.rapidapi.com"
API_URL = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"): return
    
    status_msg = await update.message.reply_text("🚀 Обробка через RapidAPI...")

    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPID_API_HOST,
        "x-rapidapi-key": RAPID_API_KEY
    }
    
    # Тіло запиту згідно з cURL
    payload = {"url": url}

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        data = response.json()

        # Розбір відповіді: зазвичай API повертає об'єкт з полем 'medias'
        medias = data.get("medias", [])
        
        video_url = None
        # Шукаємо перше доступне відео в списку medias
        for item in medias:
            if item.get("extension") == "mp4" or item.get("type") == "video":
                video_url = item.get("url")
                break
        
        # Якщо структура інша, спробуємо пряме посилання
        if not video_url:
            video_url = data.get("url") or data.get("link")

        if video_url:
            await update.message.reply_video(video=video_url, caption="✅ Готово!")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Відео не знайдено. Можливо, посилання приватне.")
            print(f"DEBUG DATA: {data}") # Побачимо структуру в логах Koyeb

    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"⚠️ Помилка API: {str(e)[:100]}")

if __name__ == '__main__':
    # Створюємо папку для логів, якщо треба
    logging.basicConfig(level=logging.INFO)
    
    # Запуск Flask
    Thread(target=run_flask).start()
    
    # Запуск Telegram бота
    token = os.environ.get('BOT_TOKEN')
    application = ApplicationBuilder().token(token).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
