import os
import requests
import logging
import re
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Налаштування логів
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask для Koyeb
app = Flask('')
@app.route('/')
def home(): return "YT-API Bot is Active", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# API Конфігурація
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
API_HOST = "yt-api.p.rapidapi.com"
API_URL = "https://yt-api.p.rapidapi.com/dl" # Ендпоінт завантаження для цього API

def extract_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'youtu\.be\/([0-9A-Za-z_-]{11})']
    for p in patterns:
        match = re.search(p, url)
        if match: return match.group(1)
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "✨ **Вітаю у Premium Downloader!** ✨\n\n"
        "Я використовую потужне **YT-API** для отримання відео.\n"
        "Просто надішли мені посилання на YouTube або Shorts."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    video_id = extract_id(url)
    
    if not video_id:
        return # Ігноруємо повідомлення без посилань

    status_msg = await update.message.reply_text("🔍 **Аналізую відео...**", parse_mode=ParseMode.MARKDOWN)

    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": API_HOST
    }
    
    try:
        # Робимо запит до YT-API для отримання посилань на завантаження
        response = requests.get(API_URL, headers=headers, params={"id": video_id}, timeout=25)
        data = response.json()
        logger.info(f"YT-API Response: {data}")

        # Це API зазвичай повертає дані у полі 'formats'
        video_url = None
        formats = data.get("formats", [])
        
        # Шукаємо найкраще відео (зазвичай воно перше в списку)
        if isinstance(formats, list):
            for f in formats:
                if f.get("url") and "video" in f.get("mimeType", ""):
                    video_url = f.get("url")
                    break

        if video_url:
            await status_msg.edit_text("🚀 **Відео знайдено! Надсилаю...**", parse_mode=ParseMode.MARKDOWN)
            try:
                await update.message.reply_video(
                    video=video_url, 
                    caption="✅ **Готово!**\n🎬 Якість: 720p/Auto",
                    parse_mode=ParseMode.MARKDOWN
                )
                await status_msg.delete()
            except Exception:
                await status_msg.edit_text(
                    f"📦 **Файл завеликий!**\n\nTelegram не дозволяє надіслати цей файл напряму, але ти можеш його завантажити:\n\n🔗 [Клікни тут]({video_url})",
                    parse_mode=ParseMode.MARKDOWN
                )
        else:
            await status_msg.edit_text("❌ **Помилка:** API не надало прямого посилання на завантаження.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("⚠️ **Технічна помилка.** Спробуйте пізніше.")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    if TOKEN:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()

