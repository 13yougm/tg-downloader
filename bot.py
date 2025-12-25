import os
import logging
import asyncio
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

# --- МІНІ-СЕРВЕР ДЛЯ RENDER (Flask краще обробляє запити) ---
server = Flask(__name__)

@server.route('/')
@server.route('/health')
def health_check():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

# Запускаємо сервер у фоні
threading.Thread(target=run_flask, daemon=True).start()
# ---------------------------------------------------------

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
MAX_SIZE = 50 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Бот онлайн! Надішли посилання на відео.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"): return
    context.user_data['url'] = url
    keyboard = [[InlineKeyboardButton("🎥 Відео", callback_data='v'), InlineKeyboardButton("🎵 MP3", callback_data='a')]]
    await update.message.reply_text("Формат:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get('url')
    await query.edit_message_text("⏳ Завантажую...")
    
    loop = asyncio.get_running_loop()
    try:
        path, title = await loop.run_in_executor(None, download_media, url, query.data)
        await query.edit_message_text("⏳ Надсилаю...")
        with open(path, 'rb') as f:
            if query.data == 'v':
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=title)
            else:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, title=title)
        await query.edit_message_text("✅ Готово!")
    except Exception as e:
        logger.error(e)
        await query.edit_message_text(f"❌ Помилка: {str(e)[:50]}")
    finally:
        if 'path' in locals() and os.path.exists(path): os.remove(path)

def download_media(url, mode):
    if not os.path.exists('downloads'): os.makedirs('downloads')
    opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }
    if os.path.exists('cookies.txt'): opts['cookiefile'] = 'cookies.txt'
    if mode == 'a':
        opts.update({'format': 'bestaudio', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]})
    else:
        opts.update({'format': 'best[ext=mp4][height<=720]/best'})

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        p = ydl.prepare_filename(info)
        if mode == 'a': p = p.rsplit('.', 1)[0] + '.mp3'
        return p, info.get('title', 'Media')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()
