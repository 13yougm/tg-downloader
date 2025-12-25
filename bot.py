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
def health(): return "ONLINE", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- КОНФІГУРАЦІЯ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# --- МЕТОД ОБХОДУ БЛОКУВАННЯ (Direct API) ---

def get_media_link(url, mode):
    """
    Використовуємо інстанс Lucatiel, який зараз найменш завантажений
    і найкраще обходить 'Sign in to confirm you are not a bot'
    """
    api_url = "https://cobalt.api.un-block.xyz/api/json"
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
    
    response = requests.post(api_url, json=payload, headers=headers, timeout=20)
    data = response.json()
    
    if data.get("status") == "error":
        raise Exception(data.get("text"))
        
    return data.get("url")

def download_file(url, mode):
    if not os.path.exists('downloads'): os.makedirs('downloads')
    path = f"downloads/file_{os.urandom(2).hex()}.{'mp3' if mode == 'a' else 'mp4'}"
    
    # Скачуємо файл через стрім, щоб не забити пам'ять Render
    res = requests.get(url, stream=True, timeout=120)
    with open(path, 'wb') as f:
        for chunk in res.iter_content(chunk_size=1024*1024):
            if chunk: f.write(chunk)
    return path

# --- ОБРОБНИКИ ТЕЛЕГРАМ ---

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if url.startswith("http"):
        context.user_data['url'] = url
        kb = [[InlineKeyboardButton("🎥 Відео", callback_data='v'),
               InlineKeyboardButton("🎵 Аудіо", callback_data='a')]]
        await update.message.reply_text("🚀 Посилання прийнято! Оберіть формат:", reply_markup=InlineKeyboardMarkup(kb))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get('url')
    mode = query.data
    
    await query.edit_message_text("⏳ Обходжу блокування YouTube... Зачекайте.")
    
    path = None
    try:
        # Крок 1: Отримуємо пряме посилання через API-дзеркало
        direct_link = await asyncio.get_running_loop().run_in_executor(None, get_media_link, url, mode)
        
        await query.edit_message_text("⏳ Файл знайдено! Починаю завантаження...")
        
        # Крок 2: Скачуємо файл на сервер
        path = await asyncio.get_running_loop().run_in_executor(None, download_file, direct_link, mode)
        
        await query.edit_message_text("🚀 Надсилаю файл у Telegram...")
        
        # Крок 3: Відправляємо користувачу
        with open(path, 'rb') as f:
            if mode == 'v':
                await context.bot.send_video(chat_id=query.message.chat_id, video=f)
            else:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
        
        await query.edit_message_text("✅ Готово! Насолоджуйтесь.")
        
    except Exception as e:
        logger.error(f"Помилка: {e}")
        await query.edit_message_text("❌ Ютуб посилив захист. Спробуйте інше відео або TikTok/Instagram.")
    finally:
        if path and os.path.exists(path):
            os.remove(path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Привіт! Скинь посилання на відео.")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Видаляємо старі запити для уникнення Conflict 409
    app.run_polling(drop_pending_updates=True)

