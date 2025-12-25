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
def health(): 
    return "ONLINE", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- КОНФІГУРАЦІЯ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# --- МЕТОДИ ЗАВАНТАЖЕННЯ (ЧЕРЕЗ API) ---

def download_file(url, mode):
    if not os.path.exists('downloads'): 
        os.makedirs('downloads')
    path = f"downloads/file_{os.urandom(2).hex()}.{'mp3' if mode == 'a' else 'mp4'}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, stream=True, timeout=120, headers=headers)
    with open(path, 'wb') as f:
        for chunk in res.iter_content(chunk_size=1024*1024):
            if chunk: 
                f.write(chunk)
    return path

def try_cobalt(url, mode):
    api_url = "https://api.cobalt.tools/api/json"
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
    return download_file(data.get("url"), mode), "Cobalt API"

def try_tikwm(url, mode):
    api_url = "https://www.tikwm.com/api/"
    res = requests.post(api_url, data={'url': url}, timeout=15)
    data = res.json().get('data')
    if not data: 
        raise Exception("TikWM Fail")
    file_url = data.get('music') if mode == 'a' else data.get('play')
    if not file_url.startswith("http"): 
        file_url = "https://www.tikwm.com" + file_url
    return download_file(file_url, mode), "TikWM API"

# --- ОБРОБНИКИ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Надішліть посилання!")

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
    
    await query.edit_message_text("⏳ Опрацьовую посилання через хмарні сервіси...")
    
    path = None
    try:
        if "tiktok.com" in url or "douyin.com" in url:
            try: 
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_tikwm, url, mode)
            except: 
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_cobalt, url, mode)
        else:
            try: 
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_cobalt, url, mode)
            except: 
                path, srv = await asyncio.get_running_loop().run_in_executor(None, try_tikwm, url, mode)

        await query.edit_message_text(f"🚀 Файл отримано ({srv})! Надсилаю...")
        with open(path, 'rb') as f:
            if mode == 'v': 
                await context.bot.send_video(chat_id=query.message.chat.id, video=f)
            else: 
                await context.bot.send_audio(chat_id=query.message.chat.id, audio=f)
        await query.edit_message_text("✅ Готово!")
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.edit_message_text("❌ На жаль, YouTube заблокував цей запит. Спробуйте інше відео або TikTok.")
    finally:
        if path and os.path.exists(path): 
            os.remove(path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    app.run_polling(drop_pending_updates=True)


