import os
import tempfile
import subprocess
import shutil
import base64
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="YouTube Audio Downloader")

# Verifica se ffmpeg está instalado (opcional, mas útil para debug)
FFMPEG_PATH = shutil.which("ffmpeg")
if not FFMPEG_PATH:
    print("⚠️  ffmpeg não encontrado!")

class DownloadResponse(BaseModel):
    success: bool
    audio_base64: Optional[str] = None
    error: Optional[str] = None
    fallback_used: Optional[str] = None

@app.get("/download")
async def download_audio(url: str = Query(..., description="URL do YouTube")):
    """
    Baixa o áudio do YouTube via yt-dlp e retorna o arquivo MP3 codificado em base64.
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL não fornecida")

    try:
        # Cria um arquivo temporário para o MP3
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            output_path = tmp.name

        # Comando yt-dlp para extrair áudio em MP3 (melhor qualidade)
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "0",       # melhor qualidade
            "-o", output_path,
            "--no-playlist",
            url
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)

        # Verifica se o arquivo foi gerado e tem tamanho
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            # Lê o arquivo e codifica em base64
            with open(output_path, "rb") as f:
                audio_data = f.read()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')

            # Remove o arquivo temporário
            os.unlink(output_path)

            return DownloadResponse(
                success=True,
                audio_base64=audio_base64,
                fallback_used="yt-dlp"
            )
        else:
            return DownloadResponse(success=False, error="Arquivo MP3 vazio ou não gerado")

    except subprocess.TimeoutExpired:
        return DownloadResponse(success=False, error="Tempo limite excedido (120s)")
    except subprocess.CalledProcessError as e:
        # Extrai a mensagem de erro do stderr
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        return DownloadResponse(success=False, error=f"Erro no yt-dlp: {error_msg}")
    except Exception as e:
        return DownloadResponse(success=False, error=f"Erro inesperado: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "ffmpeg_available": FFMPEG_PATH is not None}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)