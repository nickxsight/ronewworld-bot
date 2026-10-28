FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends libopus0 ffmpeg && rm -rf /var/lib/apt/lists/*
COPY bot.py events.json alert.wav ./
CMD ["python", "bot.py"]
