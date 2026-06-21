FROM python:3.12-slim

# Instala ffmpeg, yt-dlp e deno (JavaScript runtime)
RUN apt-get update && apt-get install -y ffmpeg curl unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    pip install yt-dlp

# Adiciona deno ao PATH
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]