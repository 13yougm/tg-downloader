FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Цей рядок каже Render, що ми слухаємо порт, навіть якщо це не так
ENV PORT=8080
EXPOSE 8080

CMD ["python", "bot.py"]
