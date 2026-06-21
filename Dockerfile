FROM python:3.12-slim

# Instala ffmpeg e yt-dlp
RUN apt-get update && apt-get install -y ffmpeg && pip install yt-dlp

WORKDIR /app

# Copia e instala as dependências
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia o código fonte
COPY . .

# Expõe a porta (opcional, mas boa prática)
EXPOSE 10000

# Comando de inicialização
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]