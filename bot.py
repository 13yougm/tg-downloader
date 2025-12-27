import os
import requests
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Налаштування логування для відстеження помилок у консолі Koyeb
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask-сервер, щоб Koyeb не вимикав бота через відсутність активності на порті
app = Flask('')
@app.route('/')
def home(): return "Бот працює на RapidAPI", 200
def run_flask(): 
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)

# Дані RapidAPI, які ти знайшов
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "social-download-all-in-one.p.rapidapi.com"
API_URL = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or not url.startswith("http"):
        return
    
    status_msg = await update.message.reply_text("⏳ Обробка посилання через сервер...")

    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPID_API_HOST,
        "x-rapidapi-key": RAPID_API_KEY
    }
    
    payload = {"url": url}

    try:
        # Запит до API
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        data = response.json()

        # Логування відповіді для налагодження (бачно в логах Koyeb)
        logger.info(f"API Response: {data}")

        # Перевірка на помилку від самого сервісу
        if data.get("status") == "error" or "error" in data:
            error_text = data.get("message") or data.get("error", "Unknown error")
            await status_msg.edit_text(f"❌ Помилка сервісу: {error_text}")
            return

        # Пошук прямого посилання на відео
        video_url = None
        medias = data.get("medias", [])
        
        # Спершу шукаємо в списку медіафайлів
        if isinstance(medias, list):
            for item in medias:
                # Шукаємо mp4 відео (зазвичай це найкраща якість)
                if item.get("type") == "video" or item.get("extension") == "mp4":
                    video_url = item.get("url")
                    break
        
        # Якщо в medias нічого немає, перевіряємо кореневі ключі
        if not video_url:
            video_url = data.get("url") or data.get("link") or data.get("download_url")

        if video_url:
            try:
                # Надсилаємо відео файлом
                await update.message.reply_video(video=video_url, caption="✅ Завантажено успішно!")
                await status_msg.delete()
            except Exception:
                # Якщо Telegram не може завантажити посилання (наприклад, воно завелике)
                await status_msg.edit_text(f"✅ Посилання знайдено, але Telegram не зміг завантажити файл.\n\n🔗 [Натисніть тут, щоб завантажити]({video_url})", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ Не вдалося отримати пряме посилання на відео.")

    except Exception as e:
        logger.error(f"General error: {e}")
        await status_msg.edit_text(f"⚠️ Помилка з'єднання: {str(e)[:100]}")

if __name__ == '__main__':
    # Запуск веб-сервера у фоновому потоці
    Thread(target=run_flask).start()
    
    # Запуск Telegram-бота
    TOKEN = os.environ.get('BOT_TOKEN')
    if not TOKEN:
        print("ПОМИЛКА: Немає BOT_TOKEN в змінних оточення!")
    else:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()
