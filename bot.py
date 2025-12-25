import os
import asyncio
import yt_dlp
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask для Koyeb (щоб сервіс не падав)
app = Flask('')
@app.route('/')
def home(): return "Бот працює!", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

TOKEN = os.environ.get('BOT_TOKEN')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "http" not in url: return
    
    status = await update.message.reply_text("⏳ Обробка посилання...")

    # Налаштування yt-dlp згідно з документацією (Варіант Б)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        # Підміна User-Agent для обходу базових блокувань Instagram/YouTube
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Використовуємо asyncio.to_thread для синхронної функції download
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            file_path = ydl.prepare_filename(info)
            
            # Перевірка розширення після ffmpeg-обробки
            if not os.path.exists(file_path):
                file_path = file_path.rsplit('.', 1)[0] + '.mp4'

        with open(file_path, 'rb') as video_file:
            await update.message.reply_video(video=video_file, caption="✅ Готово!")
        
        # Видаляємо файл після відправки
        os.remove(file_path)
        await status.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"⚠️ Помилка: {str(e)[:100]}")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    Thread(target=run_flask).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
