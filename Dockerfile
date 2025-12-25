FROM python:3.10-slim

# Встановлюємо ffmpeg та оновлюємо сертифікати
RUN apt-get update && \
    apt-get install -y ffmpeg git ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "bot.py"]
