import os
import logging
import asyncio
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

# --- СЕРВЕР ДЛЯ RENDER ---
server = Flask(__name__)
@server.route('/')
def health(): return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- ЛОГУВАННЯ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# --- ФУНКЦІЇ ЗАВАНТАЖЕННЯ ---

def download_via_cobalt(url, mode):
    """Метод 1: Cobalt API"""
    api_url = "https://api.cobalt.tools/api/json"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "url": url,
        "videoQuality": "720",
        "downloadMode": "audio" if mode == 'a' else "video"
    }
    res = requests.post(api_url, json=payload, headers=headers, timeout=15)
    if res.status_code != 200: raise Exception(f"Cobalt error {res.status_code}")
    data = res.json()
    if data.get("status") == "error": raise Exception(data.get("text"))
    
    file_url = data.get("url")
    file_res = requests.get(file_url, stream=True, timeout=120)
    
    if not os.path.exists('downloads'): os.makedirs('downloads')
    path = f"downloads/file_{os.urandom(2).hex()}.{'mp3' if mode == 'a' else 'mp4'}"
    with open(path, 'wb') as f:
        for chunk in file_res.iter_content(chunk_size=1024*1024): f.write(chunk)
    return path, "Cobalt"

def download_yt_dlp(url, mode):
    """Метод 2: Пряме завантаження (yt-dlp)"""
    if not os.path.exists('downloads'): os.makedirs('downloads')
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'format': 'bestaudio/best' if mode == 'a' else 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    }
    if mode == 'a':
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        if mode == 'a': path = path.rsplit('.', 1)[0] + '.mp3'
        return path, info.get('title', 'Video')

# --- ОБРОБНИКИ ТЕЛЕГРАМ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішліть посилання на відео.")

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
    status = await query.edit_message_text("⏳ Завантажую...")

    loop = asyncio.get_running_loop()
    path = None
    try:
        # Спроба 1: Cobalt
        try:
            path, title = await loop.run_in_executor(None, download_via_cobalt, url, mode)
        except Exception as e:
            logger.error(f"Cobalt fail: {e}")
            # Спроба 2: yt-dlp
            await query.edit_message_text("⏳ Cobalt не зміг, пробую інший метод...")
            path, title = await loop.run_in_executor(None, download_yt_dlp, url, mode)

        await query.edit_message_text("⏳ Надсилаю у Telegram...")
        with open(path, 'rb') as f:
            if mode == 'v': await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=title)
            else: await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, title=title)
        await query.edit_message_text("✅ Готово!")

    except Exception as e:
        logger.error(f"Final error: {e}")
        await query.edit_message_text(f"❌ Не вдалося завантажити. Ютуб блокує запит. Спробуйте інше посилання.")
    finally:
        if path and os.path.exists(path): os.remove(path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling(drop_pending_updates=True)
