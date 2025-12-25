FROM python:3.10-slim

# Встановлюємо системні залежності та оновлюємо сертифікати
RUN apt-get update && \
    apt-get install -y ffmpeg git ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Додатково оновлюємо сертифікати Python
RUN pip install --upgrade certifi

COPY . .

# Порт для Render
ENV PORT=8080
EXPOSE 8080

CMD ["python", "bot.py"]
