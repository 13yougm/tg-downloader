import os
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

# --- СЕРВЕР ДЛЯ RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- КОНФІГ ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
MAX_SIZE = 50 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Надішліть посилання на відео.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"): return
    context.user_data['url'] = url
    kb = [[InlineKeyboardButton("🎥 Відео", callback_data='v'), InlineKeyboardButton("🎵 MP3", callback_data='a')]]
    await update.message.reply_text("Оберіть формат:", reply_markup=InlineKeyboardMarkup(kb))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get('url')
    f_type = query.data
    await query.edit_message_text("⏳ Завантаження...")
    
    try:
        path, title = await asyncio.get_running_loop().run_in_executor(None, download, url, f_type)
        await query.edit_message_text("⏳ Надсилання...")
        with open(path, 'rb') as f:
            if f_type == 'v': await context.bot.send_video(query.message.chat_id, f, caption=title)
            else: await context.bot.send_audio(query.message.chat_id, f, title=title)
        await query.edit_message_text("✅ Готово!")
    except Exception as e:
        await query.edit_message_text(f"❌ Помилка: SSL/Network error. Спробуйте ще раз.")
    finally:
        if 'path' in locals() and os.path.exists(path): os.remove(path)

def download(url, mode):
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'nocheckcertificate': True,  # Пряме вимкнення перевірки SSL
        'no_check_certificate': True, # Подвійний контроль
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }
    
    if os.path.exists('cookies.txt'): opts['cookiefile'] = 'cookies.txt'
    
    if mode == 'a':
        opts.update({'format': 'bestaudio', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]})
    else:
        opts.update({'format': 'best[ext=mp4][height<=720]/best'})

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        if mode == 'a': path = path.rsplit('.', 1)[0] + '.mp3'
        return path, info.get('title', 'Media')

if __name__ == '__main__':
    ApplicationBuilder().token(TOKEN).build().run_polling()
