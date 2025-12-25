import os
import logging
import asyncio
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

# --- СЕРВЕР ДЛЯ RENDER (Health Check) ---
server = Flask(__name__)

@server.route('/')
def health():
    return "Бот працює!", 200

def run_flask():
    # Render автоматично надає порт через змінну середовища PORT
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

# Запускаємо веб-сервер у фоновому режимі
threading.Thread(target=run_flask, daemon=True).start()

# --- КОНФІГУРАЦІЯ БОТА ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Я готовий завантажувати відео з YouTube, TikTok, Instagram та Douyin.\n\nПросто надішліть мені посилання!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        return
    
    context.user_data['url'] = url
    keyboard = [
        [InlineKeyboardButton("🎥 Відео", callback_data='v'),
         InlineKeyboardButton("🎵 Аудіо (MP3)", callback_data='a')]
    ]
    await update.message.reply_text("Оберіть формат для завантаження:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('url')
    mode = query.data
    
    status_msg = await query.edit_message_text("⏳ Починаю завантаження... Почекайте, будь ласка.")
    
    loop = asyncio.get_running_loop()
    try:
        # Спочатку пробуємо через Cobalt API (найбільш надійний метод)
        try:
            path, title = await loop.run_in_executor(None, download_via_cobalt, url, mode)
        except Exception as e:
            logger.warning(f"Cobalt API failed, trying yt-dlp: {e}")
            # Якщо API не спрацював, пробуємо класичний yt-dlp
            path, title = await loop.run_in_executor(None, download_yt_dlp, url, mode)

        await query.edit_message_text("⏳ Надсилаю файл у Telegram...")
        
        with open(path, 'rb') as f:
            if mode == 'v':
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=title)
            else:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, title=title)
        
        await query.edit_message_text("✅ Завантаження завершено!")
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.edit_message_text(f"❌ Вибачте, сталася помилка: {str(e)[:100]}")
    finally:
        if 'path' in locals() and os.path.exists(path):
            try: os.remove(path)
            except: pass

# --- МЕТОД 1: COBALT API ---
def download_via_cobalt(url, mode):
    api_url = "https://api.cobalt.tools/api/json"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "url": url,
        "vQuality": "720",
        "isAudioOnly": True if mode == 'a' else False
    }
    
    response = requests.post(api_url, json=payload, headers=headers, timeout=30)
    data = response.json()
    
    if data.get("status") == "error":
        raise Exception(data.get("text"))
    
    file_url = data.get("url")
    file_res = requests.get(file_url, stream=True, timeout=60)
    
    if not os.path.exists('downloads'): os.makedirs('downloads')
    file_path = f"downloads/file_{mode}_{os.urandom(4).hex()}" + (".mp4" if mode == 'v' else ".mp3")
    
    with open(file_path, 'wb') as f:
        for chunk in file_res.iter_content(chunk_size=8192):
            f.write(chunk)
            
    return file_path, "Завантажено через Cobalt"

# --- МЕТОД 2: YT-DLP (Запасний) ---
def download_yt_dlp(url, mode):
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    if mode == 'a':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
        })
    else:
        ydl_opts.update({'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        if mode == 'a':
            path = path.rsplit('.', 1)[0] + '.mp3'
        return path, info.get('title', 'Media')

# --- ЗАПУСК ---
if __name__ == '__main__':
    if not TOKEN:
        raise ValueError("BOT_TOKEN не знайдено в змінних середовища!")
        
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Бот запускається з drop_pending_updates=True...")
    # drop_pending_updates=True — очищує всі старі повідомлення, щоб не було конфлікту
    app.run_polling(drop_pending_updates=True)
