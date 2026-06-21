FROM python:3.12-slim

# Instala o ffmpeg e o yt-dlp
RUN apt-get update && apt-get install -y ffmpeg && pip install yt-dlp

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]