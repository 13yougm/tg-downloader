import os
import logging
import asyncio
import threading
import os.path
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

# --- СЕРВЕР ДЛЯ RENDER ---
server = Flask(__name__)
@server.route('/')
def health(): return "ONLINE", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- КОНФІГУРАЦІЯ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# --- ФУНКЦІЯ ЗАВАНТАЖЕННЯ ---
def download_media(url, mode):
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    # Налаштування для обходу блокувань
    ydl_opts = {
        'format': 'bestaudio/best' if mode == 'a' else 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/%(id)s_{os.urandom(2).hex()}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'add_header': [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language: en-US,en;q=0.5',
        ],
    }

    if mode == 'a':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        if mode == 'a':
            file_path = file_path.rsplit('.', 1)[0] + '.mp3'
        return file_path

# --- ОБРОБНИКИ ТЕЛЕГРАМ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Бот знову в строю! Надішліть посилання на відео.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if url.startswith("http"):
        context.user_data['url'] = url
        kb = [[InlineKeyboardButton("🎥 Відео", callback_data='v'), InlineKeyboardButton("🎵 Аудіо", callback_data='a')]]
        await update.message.reply_text("Оберіть формат:", reply_markup=InlineKeyboardMarkup(kb))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get('url')
    mode = query.data
    
    status = await query.edit_message_text("⏳ Починаю завантаження... Це може зайняти до 2-х хвилин.")
    
    path = None
    try:
        # Запускаємо завантаження в окремому потоці, щоб не блокувати бота
        path = await asyncio.get_running_loop().run_in_executor(None, download_media, url, mode)
        
        await query.edit_message_text("🚀 Файл завантажено на сервер! Надсилаю в чат...")
        with open(path, 'rb') as f:
            if mode == 'v':
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, read_timeout=120, write_timeout=120)
            else:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, read_timeout=120, write_timeout=120)
        
        await query.edit_message_text("✅ Готово!")
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Помилка: Ютуб заблокував цей запит. Спробуйте інше посилання або TikTok.")
    finally:
        if path and os.path.exists(path):
            os.remove(path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling(drop_pending_updates=True)

