import os
import asyncio
import yt_dlp
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Налаштування логів
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask для Koyeb (щоб сервіс був Healthy)
app = Flask('')
@app.route('/')
def home(): return "Бот активний", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

TOKEN = os.environ.get('BOT_TOKEN')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"): return
    
    status = await update.message.reply_text("⏳ Обробка... Це може зайняти до хвилини.")

    # Налаштування згідно з офіційною документацією yt-dlp
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    try:
        # Використовуємо ThreadPoolExecutor через asyncio для завантаження
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Екстракція інфо та завантаження
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            # Отримуємо шлях до фінального файлу
            file_path = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp4'

        if os.path.exists(file_path):
            with open(file_path, 'rb') as video:
                await update.message.reply_video(video=video, caption="✅ Готово!")
            os.remove(file_path) # Очищення пам'яті
            await status.delete()
        else:
            await status.edit_text("❌ Помилка: файл не знайдено.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"⚠️ Сталася помилка: {str(e)[:100]}")

if __name__ == '__main__':
    # Створюємо папку для завантажень
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    # Запуск Flask у фоновому потоці
    Thread(target=run_flask).start()
    
    # Запуск бота
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
