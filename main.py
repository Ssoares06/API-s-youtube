import os
import tempfile
import subprocess
import base64
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="YouTube Audio Downloader")

# Caminho para o arquivo de cookies (deve estar na raiz)
COOKIES_FILE = "cookies.txt"

class DownloadResponse(BaseModel):
    success: bool
    audio_base64: Optional[str] = None
    error: Optional[str] = None
    fallback_used: Optional[str] = None

@app.get("/download")
async def download_audio(url: str = Query(..., description="URL do YouTube")):
    if not url:
        raise HTTPException(status_code=400, detail="URL não fornecida")

    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            output_path = tmp.name

        # Comando simplificado – sem flags JS, pois yt-dlp-ejs resolve automaticamente
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", output_path,
            "--no-playlist",
            "--cookies", COOKIES_FILE,
            url
        ]

        # Fallback opcional: se falhar, tenta com --remote-components ejs:npm
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        except subprocess.CalledProcessError as e:
            # Se o erro mencionar "Requested format is not available", tenta o fallback
            if "Requested format is not available" in e.stderr.decode('utf-8'):
                cmd_fallback = cmd + ["--remote-components", "ejs:npm"]
                subprocess.run(cmd_fallback, check=True, capture_output=True, timeout=300)
            else:
                raise

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with open(output_path, "rb") as f:
                audio_data = f.read()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            os.unlink(output_path)

            return DownloadResponse(
                success=True,
                audio_base64=audio_base64,
                fallback_used="yt-dlp"
            )
        else:
            return DownloadResponse(success=False, error="Arquivo MP3 vazio")

    except subprocess.TimeoutExpired:
        return DownloadResponse(success=False, error="Tempo limite excedido (300s)")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        return DownloadResponse(success=False, error=f"Erro no yt-dlp: {error_msg}")
    except Exception as e:
        return DownloadResponse(success=False, error=f"Erro inesperado: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "cookies_exist": os.path.exists(COOKIES_FILE)}