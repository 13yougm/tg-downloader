import os
import requests
import logging
import re
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Налаштування логів
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask для Koyeb
app = Flask('')
@app.route('/')
def home(): return "YouTube Bot is Online", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

# API Data
RAPID_API_KEY = "f34d963ae4msh8d0868c59a60488p1d3362jsn35a7e001db2a"
RAPID_API_HOST = "social-media-video-downloader.p.rapidapi.com"
API_URL = "https://social-media-video-downloader.p.rapidapi.com/youtube/v3/video/details"

def extract_video_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'youtu\.be\/([0-9A-Za-z_-]{11})']
    for p in patterns:
        match = re.search(p, url)
        if match: return match.group(1)
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Гарне привітання"""
    user_name = update.effective_user.first_name
    welcome_text = (
        f"👋 **Привіт, {user_name}!**\n\n"
        "🎬 Я допоможу тобі завантажити відео з **YouTube** у високій якості.\n\n"
        "📌 **Як користуватися:**\n"
        "Просто надішли мені посилання на відео або Shorts."
    )
    keyboard = [[InlineKeyboardButton("Developer 👨‍💻", url="https://t.me/your_username")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or "http" not in url: return
    
    video_id = extract_video_id(url)
    if not video_id:
        await update.message.reply_text("❌ **Помилка:** Не вдалося розпізнати посилання. Спробуй ще раз.", parse_mode=ParseMode.MARKDOWN)
        return

    # Динамічний статус
    status_msg = await update.message.reply_text("📥 **Обробка...** \n[▓▓▓░░░░░░░] 30%", parse_mode=ParseMode.MARKDOWN)

    params = {
        "videoId": video_id,
        "renderableFormats": "720p,highres",
        "urlAccess": "proxied",
        "getTranscript": "false"
    }
    headers = {"x-rapidapi-key": RAPID_API_KEY, "x-rapidapi-host": RAPID_API_HOST}

    try:
        await status_msg.edit_text("⚡ **Завантаження...** \n[▓▓▓▓▓▓░░░░] 60%", parse_mode=ParseMode.MARKDOWN)
        response = requests.get(API_URL, headers=headers, params=params, timeout=30)
        data = response.json()

        video_url = None
        formats = data.get("formats", [])
        if isinstance(formats, list):
            for f in formats:
                if f.get("url"):
                    video_url = f.get("url")
                    break

        if video_url:
            await status_msg.edit_text("✅ **Готово! Надсилаю...** \n[▓▓▓▓▓▓▓▓▓▓] 100%", parse_mode=ParseMode.MARKDOWN)
            try:
                await update.message.reply_video(
                    video=video_url, 
                    caption="🎬 **Ось твоє відео!**\n\n🚀 Згенеровано через @ТвійБот",
                    parse_mode=ParseMode.MARKDOWN
                )
                await status_msg.delete()
            except Exception:
                await status_msg.edit_text(
                    f"✨ **Відео знайдено!**\n\nФайл завеликий для прямої відправки, але ти можеш його завантажити:\n\n🔗 [Клікни сюди для завантаження]({video_url})", 
                    parse_mode=ParseMode.MARKDOWN
                )
        else:
            await status_msg.edit_text("📭 **Вибачте**, але це відео недоступне для завантаження через проксі.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("⚠️ **Виникла технічна помилка.** Спробуй пізніше.")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    if TOKEN:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling()

