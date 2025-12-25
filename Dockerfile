FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y ffmpeg git ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONHTTPSVERIFY=0

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade certifi

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "bot.py"]
