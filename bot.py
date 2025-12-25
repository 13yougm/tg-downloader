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
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

# Запускаємо веб-сервер у фоновому режимі
threading.Thread(target=run_flask, daemon=True).start()

# --- КОНФІГУРАЦІЯ БОТА ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Я допоможу тобі завантажити відео.\n\nПросто надішли посилання з YouTube, Instagram або TikTok!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        return
    
    context.user_data['url'] = url
    keyboard = [
        [InlineKeyboardButton("🎥 Відео", callback_data='v'),
         InlineKeyboardButton("🎵 Аудіо (MP3)", callback_data='a')]
    ]
    await update.message.reply_text("Оберіть формат:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('url')
    mode = query.data
    
    status_msg = await query.edit_message_text("⏳ Готую посилання через Cobalt API...")
    
    loop = asyncio.get_running_loop()
    try:
        # Пріоритет: Cobalt API (працює без cookies)
        try:
            path, title = await loop.run_in_executor(None, download_via_cobalt, url, mode)
        except Exception as e:
            logger.warning(f"Cobalt error: {e}. Falling back to yt-dlp.")
            await query.edit_message_text(f"⚠️ Cobalt не зміг, пробую пряме завантаження...")
            path, title = await loop.run_in_executor(None, download_yt_dlp, url, mode)

        await query.edit_message_text("⏳ Надсилаю файл у Telegram...")
        
        with open(path, 'rb') as f:
            if mode == 'v':
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=title)
            else:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, title=title)
        
        await query.edit_message_text("✅ Готово!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Помилка: {str(e)[:100]}")
    finally:
        if 'path' in locals() and os.path.exists(path):
            try: os.remove(path)
            except: pass

# --- МЕТОД 1: COBALT API (Актуальна версія) ---
def download_via_cobalt(url, mode):
    api_url = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Оновлений формат payload для Cobalt API v10+
    payload = {
        "url": url,
        "videoQuality": "720",
        "filenameStyle": "pretty",
        "downloadMode": "audio" if mode == 'a' else "video"
    }
    
    response = requests.post(api_url, json=payload, headers=headers, timeout=20)
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}")
        
    data = response.json()
    
    if data.get("status") == "error":
        raise Exception(data.get("text"))
    
    file_url = data.get("url")
    if not file_url:
        raise Exception("Не вдалося отримати посилання на файл")
        
    file_res = requests.get(file_url, stream=True, timeout=120)
    
    if not os.path.exists('downloads'): os.makedirs('downloads')
    file_path = f"downloads/file_{mode}_{os.urandom(2).hex()}" + (".mp4" if mode == 'v' else ".mp3")
    
    with open(file_path, 'wb') as f:
        for chunk in file_res.iter_content(chunk_size=1024*1024): # 1MB chunks
            if chunk: f.write(chunk)
            
    return file_path, "Завантажено успішно"

# --- МЕТОД 2: YT-DLP (Запасний) ---
def download_yt_dlp(url, mode):
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'nocheckcertificate': True,
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

if __name__ == '__main__':
    if not TOKEN:
        raise ValueError("BOT_TOKEN missing!")
        
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Бот готовий до роботи...")
    app.run_polling(drop_pending_updates=True)
