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
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- КОНФІГ ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
MAX_SIZE = 50 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Бот з підтримкою Cobalt API! Надішли посилання.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"): return
    context.user_data['url'] = url
    kb = [[InlineKeyboardButton("🎥 Відео", callback_data='v'), InlineKeyboardButton("🎵 MP3", callback_data='a')]]
    await update.message.reply_text("Обери формат:", reply_markup=InlineKeyboardMarkup(kb))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get('url')
    mode = query.data
    await query.edit_message_text("⏳ Завантаження через API...")

    try:
        path, title = await asyncio.get_running_loop().run_in_executor(None, download_via_cobalt, url, mode)
        await query.edit_message_text("⏳ Надсилання...")
        with open(path, 'rb') as f:
            if mode == 'v': await context.bot.send_video(query.message.chat_id, f, caption=title)
            else: await context.bot.send_audio(query.message.chat_id, f, title=title)
        await query.edit_message_text("✅ Готово!")
    except Exception as e:
        # Якщо Cobalt не зміг, пробуємо класичний метод yt-dlp як запасний
        try:
            await query.edit_message_text("⏳ API не зміг, пробую класичний метод...")
            path, title = await asyncio.get_running_loop().run_in_executor(None, download_yt_dlp, url, mode)
            with open(path, 'rb') as f:
                if mode == 'v': await context.bot.send_video(query.message.chat_id, f, caption=title)
                else: await context.bot.send_audio(query.message.chat_id, f, title=title)
            await query.edit_message_text("✅ Готово (через запасний метод)!")
        except Exception as e2:
            await query.edit_message_text(f"❌ Помилка: Сервіс тимчасово недоступний.")
    finally:
        if 'path' in locals() and os.path.exists(path): os.remove(path)

# --- МЕТОД 1: COBALT API (Основний) ---
def download_via_cobalt(url, mode):
    # Використовуємо офіційний API Cobalt
    api_url = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "vQuality": "720",
        "isAudioOnly": True if mode == 'a' else False
    }
    
    response = requests.post(api_url, json=payload, headers=headers)
    data = response.json()
    
    if data.get("status") == "error":
        raise Exception(data.get("text"))
    
    file_url = data.get("url")
    file_res = requests.get(file_url, stream=True)
    file_path = f"downloads/file_{mode}.mp4" if mode == 'v' else f"downloads/file_{mode}.mp3"
    
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    with open(file_path, 'wb') as f:
        for chunk in file_res.iter_content(chunk_size=8192):
            f.write(chunk)
            
    return file_path, "Завантажено через Cobalt"

# --- МЕТОД 2: YT-DLP (Запасний) ---
def download_yt_dlp(url, mode):
    if not os.path.exists('downloads'): os.makedirs('downloads')
    opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'nocheckcertificate': True,
        'quiet': True,
        'format': 'bestvideo[height<=720]+bestaudio/best' if mode == 'v' else 'bestaudio/best',
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        p = ydl.prepare_filename(info)
        return p, info.get('title', 'Media')

if __name__ == '__main__':
    ApplicationBuilder().token(TOKEN).build().run_polling()
