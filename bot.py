import os
import logging
import asyncio
import yt_dlp
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask для Health Check на Koyeb (порт 8000)
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# Налаштування токена
TOKEN = os.environ.get('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішліть посилання на YouTube, TikTok або Instagram, і я завантажу відео для вас.")

async def download_video(url):
    """Завантаження відео через yt-dlp"""
    ydl_opts = {
        'format': 'best[ext=mp4]/best', # Вибираємо найкращий mp4
        'outtmpl': 'video.mp4',         # Тимчасова назва файлу
        'quiet': True,
        'max_filesize': 45 * 1024 * 1024 # Обмеження 45МБ для Telegram
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return 'video.mp4'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "http" not in url:
        return

    status_msg = await update.message.reply_text("⏳ Завантажую... зачекайте кілька секунд.")

    try:
        # Виконуємо завантаження у фоновому режимі, щоб не блокувати бота
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL({'format': 'best[ext=mp4]', 'outtmpl': 'video.mp4', 'quiet': True}).download([url]))
        
        # Відправка відео
        with open('video.mp4', 'rb') as video:
            await update.message.reply_video(video=video, caption="Ваше відео готове! ✅")
        
        await status_msg.delete()
        os.remove('video.mp4') # Видаляємо файл після відправки

    except Exception as e:
        logger.error(f"Помилка: {e}")
        await status_msg.edit_text("❌ Не вдалося завантажити відео. Можливо, файл занадто великий або посилання невірне.")

if __name__ == '__main__':
    # Запуск Flask у фоні
    Thread(target=run_flask).start()
    
    # Запуск бота
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот версії 1.2 з підтримкою YouTube запущений!")
    application.run_polling()
