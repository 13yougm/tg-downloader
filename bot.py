import os
import logging
import asyncio
import yt_dlp
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home(): return "OK", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

TOKEN = os.environ.get('BOT_TOKEN')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "http" not in url: return
    
    status = await update.message.reply_text("⏳ Завантажую... (через резервний канал)")

    # КРОК 1: Пробуємо Cobalt API (найкраще для Douyin/YouTube на хостингах)
    try:
        r = requests.post("https://api.cobalt.tools/api/json", 
                         json={"url": url, "vCodec": "h264", "vQuality": "720"}, 
                         headers={"Accept": "application/json", "Content-Type": "application/json"},
                         timeout=15)
        data = r.json()
        
        if data.get("url"):
            await update.message.reply_video(video=data.get("url"), caption="Готово! ✅")
            await status.delete()
            return
        elif data.get("status") == "picker":
            for item in data.get("picker"):
                await update.message.reply_photo(photo=item.get("url"))
            await status.delete()
            return
    except Exception as e:
        logger.info(f"Cobalt skip: {e}")

    # КРОК 2: Якщо Cobalt не зміг, пробуємо самі через yt-dlp
    await status.edit_text("⏳ Cobalt не відповів, пробуємо пряме завантаження...")
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': 'vid.mp4',
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
        
        if os.path.exists('vid.mp4'):
            with open('vid.mp4', 'rb') as v:
                await update.message.reply_video(video=v, caption="Завантажено напряму! ✅")
            os.remove('vid.mp4')
            await status.delete()
        else:
            raise Exception("File not found")
    except Exception as e:
        logger.error(f"Final error: {e}")
        await status.edit_text("❌ На жаль, YouTube/Douyin заблокували запит. Спробуйте Shorts або пізніше.")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Кидай посилання на YouTube, TikTok або Douyin!")))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.run_polling()
