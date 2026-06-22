import os
import re
import time
import tempfile
import subprocess
import base64
import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="YouTube Audio Downloader")

# ===== CONFIGURAÇÃO DA RAPIDAPI =====
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "c6c0e393ecmsh8ee3d8fa16449e9p19dab9jsn5864d027ed5b")
RAPIDAPI_HOST = "youtube-mp3-audio-video-downloader.p.rapidapi.com"
ENDPOINT_PATH = "/get_mp3_download_link"
QUALITY = "low"
WAIT_UNTIL_READY = True   # Aguarda o arquivo ficar pronto (até 300s)
# =====================================

COOKIES_FILE = "cookies.txt"  # fallback, se necessário

class DownloadResponse(BaseModel):
    success: bool
    audio_base64: Optional[str] = None
    error: Optional[str] = None
    fallback_used: Optional[str] = None

def extract_video_id(url: str) -> str:
    """Extrai o ID do vídeo de uma URL do YouTube."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&]|$)',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Não foi possível extrair o video_id da URL: {url}")

def download_via_rapidapi(url: str):
    """Tenta baixar o áudio usando a API da RapidAPI."""
    video_id = extract_video_id(url)
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }
    params = {
        "quality": QUALITY,
        "wait_until_the_file_is_ready": "true" if WAIT_UNTIL_READY else "false"
    }
    
    full_url = f"https://{RAPIDAPI_HOST}{ENDPOINT_PATH}/{video_id}"
    print(f"🔗 Chamando: {full_url} com params: {params}")
    
    response = requests.get(full_url, headers=headers, params=params, timeout=300)
    
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
    
    data = response.json()
    print(f"📦 Resposta da API: {data}")
    
    # Extrai o link de download
    download_url = data.get("file") or data.get("reserved_file")
    if not download_url:
        raise Exception(f"Nenhum link de download encontrado. Resposta: {data}")
    
    # Se wait_until_the_file_is_ready for false, o link pode retornar 404 inicialmente.
    # Nesse caso, fazemos algumas tentativas com pausa.
    if not WAIT_UNTIL_READY:
        max_attempts = 10
        for attempt in range(max_attempts):
            mp3_response = requests.get(download_url, timeout=60)
            if mp3_response.status_code == 200:
                return mp3_response.content
            print(f"⏳ Tentativa {attempt+1}/{max_attempts}: MP3 ainda não disponível. Aguardando 30s...")
            time.sleep(30)
        raise Exception("Tempo esgotado aguardando o arquivo MP3 ficar pronto.")
    else:
        # Se wait_until_ready for true, a API já esperou, então baixamos direto.
        mp3_response = requests.get(download_url, timeout=60)
        if mp3_response.status_code != 200:
            raise Exception(f"Falha ao baixar MP3: HTTP {mp3_response.status_code}")
        return mp3_response.content

def download_via_ytdlp(url: str):
    """Fallback: tenta baixar usando yt-dlp com cookies."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        output_path = tmp.name

    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_path,
        "--no-playlist",
        "--cookies", COOKIES_FILE,
        url
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        with open(output_path, "rb") as f:
            audio_data = f.read()
        os.unlink(output_path)
        return audio_data
    else:
        raise Exception("Arquivo MP3 vazio ou não gerado")

@app.get("/download")
async def download_audio(url: str = Query(..., description="URL do YouTube")):
    if not url:
        raise HTTPException(status_code=400, detail="URL não fornecida")

    # Estratégia 1: RapidAPI
    try:
        audio_content = download_via_rapidapi(url)
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        return DownloadResponse(
            success=True,
            audio_base64=audio_base64,
            fallback_used="RapidAPI"
        )
    except Exception as e:
        print(f"⚠️ RapidAPI falhou: {str(e)}")
        # Se falhar, tenta o fallback com yt-dlp

    # Estratégia 2: yt-dlp com cookies (fallback)
    try:
        audio_content = download_via_ytdlp(url)
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        return DownloadResponse(
            success=True,
            audio_base64=audio_base64,
            fallback_used="yt-dlp"
        )
    except Exception as e:
        return DownloadResponse(
            success=False,
            error=f"Todas as tentativas falharam. Último erro: {str(e)}"
        )

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "rapidapi_configured": bool(RAPIDAPI_KEY),
        "cookies_exist": os.path.exists(COOKIES_FILE)
    }