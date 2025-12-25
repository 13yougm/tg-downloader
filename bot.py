import os
import logging
import asyncio
import threading
import requests
import os.path
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --- СЕРВЕР ДЛЯ RENDER ---
server = Flask(__name__)
@server.route('/')
def health(): return "Статус: Бот онлайн", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- КОНФІГУРАЦІЯ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# --- МЕТОДИ ЗАВАНТАЖЕННЯ ---

def download_file(url, mode):
    """Скачування файлу за прямим посиланням"""
    if not os.path.exists('downloads'): os.makedirs('downloads')
    ext = "mp3" if mode == 'a' else "mp4"
    path = f"downloads/file_{os.urandom(2).hex()}.{ext}"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    res = requests.get(url, stream=True, timeout=120, headers=headers)
    with open(path, 'wb') as f:
        for chunk in res.iter_content(chunk_size=1024*1024):
            if chunk: f.write(chunk)
    return path

def try_cobalt(url, mode):
    """Метод 1: Оновлений Cobalt API (Обхід помилки v7)"""
    # Ми використовуємо той самий URL, але НОВУ структуру даних
    api_url = "https://api.cobalt.tools/api/json"
    
    # ЦІ ЗАГОЛОВКИ ОБОВ'ЯЗКОВІ, щоб не було помилки v7
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://cobalt.tools",
        "Referer": "https://cobalt.tools/"
    }
    
    payload = {
        "url": url,
        "videoQuality": "720",
        "downloadMode": "audio" if mode == 'a' else "video",
        "filenameStyle": "pretty"
    }
    
    res = requests.post(api_url, json=payload, headers=headers, timeout=20)
    data = res.json()
    
    if data.get("status") == "error": 
        raise Exception(data.get("text"))
    
    return download_file(data.get("url"), mode), "Cobalt (v10 Logic)"

def try_tikwm(url, mode):
    """Метод 2: TikWM API (Ідеально для TikTok/Douyin, як tiqu.cc)"""
    api_url = "https://www.tikwm.com/api/"
    res = requests.post(api_url, data={'url': url}, timeout=20)
    res_data = res.json()
    
    if not res_data.get('data'): 
        raise Exception("TikWM error")
    
    data = res_data['data']
    file_url = data.get('music') if mode == 'a' else data.get('play')
    
    if not file_url.startswith("http"):
        file_url = "https://www.tikwm.com" + file_url
        
    return download_file(file_url, mode), "TikWM/Tiqu"

# --- ОБРОБНИКИ ТЕЛЕГРАМ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Бот виправлений! Тепер працює YouTube та Douyin.")

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
    
    await query.edit_message_text("⏳ Завантажую... Це займе кілька секунд.")
    path = None
    
    try:
        # Авто-вибір сервісу
        if "douyin.com" in url or "tiktok.com" in url:
            try:
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_tikwm, url, mode)
            except:
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_cobalt, url, mode)
        else:
            try:
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_cobalt, url, mode)
            except:
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_tikwm, url, mode)

        await query.edit_message_text(f"🚀 Файл готовий ({srv}). Надсилаю...")
        with open(path, 'rb') as f:
            if mode == 'v': await context.bot.send_video(chat_id=query.message.chat_id, video=f)
            else: await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
        await query.edit_message_text("✅ Готово!")

    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Помилка завантаження. Спробуйте інше посилання.")
    finally:
        if path and os.path.exists(path): os.remove(path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling(drop_pending_updates=True)
