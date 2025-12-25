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

# Ліміт 50 МБ (у байтах)
MAX_SIZE = 50 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Надішли мені посилання на відео (YouTube, TikTok, Insta, FB), і я завантажу його.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    # Зберігаємо URL у контексті користувача
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

    await query.edit_message_text(f"⏳ Статус: Завантажую ({format_type})...")
    
    # Запуск важкого процесу в окремому потоці
    loop = asyncio.get_running_loop()
    try:
        file_path, title = await loop.run_in_executor(None, download_media, url, format_type)
        
        # Перевірка розміру
        if os.path.getsize(file_path) > MAX_SIZE:
            await query.edit_message_text("❌ Помилка: Файл більше 50 МБ (ліміт Telegram Bot API).")
            os.remove(file_path)
            return

        await query.edit_message_text("⏳ Статус: Відправляю...")
        
        chat_id = query.message.chat_id
        with open(file_path, 'rb') as f:
            if format_type == 'video':
                await context.bot.send_video(chat_id=chat_id, video=f, caption=f"🎥 {title}")
            else:
                await context.bot.send_audio(chat_id=chat_id, audio=f, title=title, caption=f"🎵 {title}")
        
        await query.edit_message_text("✅ Готово!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text("❌ Помилка при завантаженні/відправці. Перевірте посилання або приватність.")
    finally:
        # Очистка файлів
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            os.remove(file_path)

def download_media(url, format_type):
    """Синхронна функція завантаження через yt-dlp"""
    # Унікальне ім'я для файлу
    output_template = f'downloads/%(id)s.%(ext)s'
    
    opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': MAX_SIZE, # Спроба обмежити на рівні yt-dlp
        'restrictfilenames': True, # Без спецсимволів
    }

    if format_type == 'audio':
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # MP4 формат, не більше 1080p, щоб влізти в ліміт
        opts.update({
            'format': 'bestvideo[ext=mp4][filesize<50M]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        })

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Media')
        
        # Знаходимо завантажений файл
        if format_type == 'audio':
            # Після конвертації розширення mp3
            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
        else:
            filename = ydl.prepare_filename(info)
            
    return filename, title

if __name__ == '__main__':
    # Створюємо папку для завантажень
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is running...")
    app.run_polling()