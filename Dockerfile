# Використовуємо легкий Linux з Python
FROM python:3.10-slim

# Встановлюємо FFmpeg та git (потрібні для роботи)
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# Робоча папка всередині сервера
WORKDIR /app

# Копіюємо файли і ставимо бібліотеки
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда запуску
CMD ["python", "bot.py"]