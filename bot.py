import os
import logging
import asyncio
import glob
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Отримання токена
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN env variable is missing!")

# Ліміт 50 МБ
MAX_SIZE = 50 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Надішли мені посилання на відео (YouTube, TikTok, Insta, FB, Pinterest).")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("❌ Це не схоже на посилання.")
        return
        
    context.user_data['url'] = url
    keyboard = [
        [InlineKeyboardButton("🎥 Відео", callback_data='video')],
        [InlineKeyboardButton("🎵 Аудіо (MP3)", callback_data='audio')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Виберіть формат:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    format_type = query.data
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text("❌ Посилання втрачено. Надішліть знову.")
        return

    status_msg = await query.edit_message_text(f"⏳ Статус: Завантажую...")
    
    loop = asyncio.get_running_loop()
    try:
        # Виконуємо завантаження
        file_path, title = await loop.run_in_executor(None, download_media, url, format_type)
        
        if not file_path or not os.path.exists(file_path):
            raise Exception("Файл не знайдено після завантаження")

        if os.path.getsize(file_path) > MAX_SIZE:
            await query.edit_message_text("❌ Файл занадто великий (> 50 МБ).")
            os.remove(file_path)
            return

        await query.edit_message_text("⏳ Статус: Відправляю у Telegram...")
        
        with open(file_path, 'rb') as f:
            if format_type == 'video':
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=f"✅ {title}")
            else:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, title=title)
        
        await query.edit_message_text("✅ Готово!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        error_text = str(e)
        if "confirm you are not a bot" in error_text.lower():
            await query.edit_message_text("❌ YouTube заблокував запит. Спробуйте інше посилання або TikTok/Insta.")
        else:
            await query.edit_message_text(f"❌ Помилка: Обмежений доступ або невірне посилання.")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

def download_media(url, format_type):
    # Папка для завантажень
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    output_template = f'downloads/%(id)s.%(ext)s'
    
    # Налаштування для обходу блокувань
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        # Імітація реального браузера
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        'nocheckcertificate': True,
        'geo_bypass': True,
    }

    if format_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # Пріоритет на MP4 до 1080p, щоб не перевищити ліміт 50МБ
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Media')
        
        if format_type == 'audio':
            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
        else:
            filename = ydl.prepare_filename(info)
            
    return filename, title

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()
