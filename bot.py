import os
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

# --- СЕРВЕР ДЛЯ RENDER (Щоб не було Timed Out) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- ЛОГУВАННЯ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
MAX_SIZE = 50 * 1024 * 1024  # 50MB ліміт Telegram

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Надішли мені посилання на відео з YouTube або TikTok.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        return
    context.user_data['url'] = url
    keyboard = [
        [InlineKeyboardButton("🎥 Відео", callback_data='video')],
        [InlineKeyboardButton("🎵 Аудіо (MP3)", callback_data='audio')]
    ]
    await update.message.reply_text("Обери формат:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get('url')
    format_type = query.data
    
    status_msg = await query.edit_message_text("⏳ Завантажую... зачекайте хвилину.")
    
    loop = asyncio.get_running_loop()
    try:
        file_path, title = await loop.run_in_executor(None, download_media, url, format_type)
        
        if not file_path or not os.path.exists(file_path):
            raise Exception("Файл не знайдено.")

        if os.path.getsize(file_path) > MAX_SIZE:
            await query.edit_message_text("❌ Файл занадто великий для Telegram (>50МБ).")
            os.remove(file_path)
            return

        await query.edit_message_text("⏳ Надсилаю у Telegram...")
        with open(file_path, 'rb') as f:
            if format_type == 'video':
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=title)
            else:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, title=title)
        
        await query.edit_message_text("✅ Готово!")
    except Exception as e:
        logger.error(f"Помилка: {e}")
        await query.edit_message_text(f"❌ Помилка: {str(e)[:100]}")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

def download_media(url, format_type):
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,  # Ігноруємо помилки SSL
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # Використовуємо cookies, якщо вони є
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    if format_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        })
    else:
        # Обмежуємо якість до 720p, щоб влізти в 50МБ
        ydl_opts.update({'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if format_type == 'audio':
            filename = filename.rsplit('.', 1)[0] + '.mp3'
        return filename, info.get('title', 'Media')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()
