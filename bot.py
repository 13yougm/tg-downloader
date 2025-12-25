import os
import logging
import asyncio
import yt_dlp
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Flask для Koyeb
app = Flask('')
@app.route('/')
def home(): return "OK", 200
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

TOKEN = os.environ.get('BOT_TOKEN')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "http" not in url: return
    
    status = await update.message.reply_text("⏳ Завантажую Douyin через yt-dlp...")

    # Налаштування саме для версії 2023.11.16
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'douyin_video.mp4',
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }

    try:
        # Завантаження відео
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
        
        # Відправка відео
        if os.path.exists('douyin_video.mp4'):
            with open('douyin_video.mp4', 'rb') as v:
                await update.message.reply_video(video=v, caption="Готово! ✅ (yt-dlp)")
            os.remove('douyin_video.mp4') # Видаляємо файл після відправки
            await status.delete()
        else:
            await status.edit_text("❌ Файл не знайдено після завантаження.")

    except Exception as e:
        await status.edit_text(f"⚠️ Помилка завантаження: {str(e)[:100]}")
        if os.path.exists('douyin_video.mp4'): os.remove('douyin_video.mp4')

if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Кидай посилання на Douyin!")))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot.run_polling()
