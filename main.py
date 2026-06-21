import os
import tempfile
import subprocess
import shutil
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="YouTube Audio Downloader com Fallback")

# ========== CONFIGURAÇÕES ==========
TEMP_DIR = tempfile.mkdtemp(prefix="yt_audio_")
FFMPEG_PATH = shutil.which("ffmpeg")  # Certifique-se de que o ffmpeg está instalado

# ========== MODELOS ==========
class DownloadResponse(BaseModel):
    success: bool
    audio_url: Optional[str] = None
    error: Optional[str] = None
    fallback_used: Optional[str] = None

# ========== FUNÇÃO PRINCIPAL COM FALLBACK ==========
def download_audio_with_fallback(youtube_url: str) -> tuple:
    """
    Tenta baixar o áudio usando múltiplas estratégias em sequência.
    Retorna (caminho_do_arquivo_mp3, nome_do_metodo_que_funcionou)
    """
    # --- ESTRATÉGIA 1: yt-dlp local (mais confiável) ---
    try:
        print(f"[yt-dlp] Tentando baixar: {youtube_url}")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            output_path = tmp.name
        
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "0",  # Melhor qualidade
            "-o", output_path,
            "--no-playlist",
            youtube_url
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        
        # Verifica se o arquivo foi criado e tem tamanho > 0
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path, "yt-dlp"
        else:
            raise Exception("Arquivo gerado vazio ou inexistente")
            
    except Exception as e:
        print(f"[yt-dlp] Falhou: {str(e)}")
        # Limpeza em caso de falha
        try:
            if os.path.exists(output_path):
                os.unlink(output_path)
        except:
            pass

    # --- ESTRATÉGIA 2: TornadoAPI (serviço pago com plano gratuito) ---
    try:
        print(f"[TornadoAPI] Tentando: {youtube_url}")
        # Documentação: https://tornadoapi.com/docs
        response = requests.post(
            "https://api.tornadoapi.com/v1/download",
            json={"url": youtube_url, "format": "mp3"},
            headers={"X-API-Key": os.getenv("TORNADO_API_KEY", "")},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("download_url"):
                # Baixa o MP3 da URL gerada pela TornadoAPI
                mp3_resp = requests.get(data["download_url"], timeout=60)
                if mp3_resp.status_code == 200:
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                        tmp.write(mp3_resp.content)
                        return tmp.name, "TornadoAPI"
        raise Exception("Resposta inválida da TornadoAPI")
    except Exception as e:
        print(f"[TornadoAPI] Falhou: {str(e)}")

    # --- ESTRATÉGIA 3: RapidAPI (Super Fast YouTube to MP3) ---
    try:
        print(f"[RapidAPI] Tentando: {youtube_url}")
        # Exemplo de endpoint - substitua pela sua chave e host
        response = requests.get(
            "https://youtube-mp3-downloader2.p.rapidapi.com/ytmp3",
            params={"url": youtube_url},
            headers={
                "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", ""),
                "X-RapidAPI-Host": "youtube-mp3-downloader2.p.rapidapi.com"
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("link"):
                mp3_resp = requests.get(data["link"], timeout=60)
                if mp3_resp.status_code == 200:
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                        tmp.write(mp3_resp.content)
                        return tmp.name, "RapidAPI"
        raise Exception("Resposta inválida da RapidAPI")
    except Exception as e:
        print(f"[RapidAPI] Falhou: {str(e)}")

    # --- ESTRATÉGIA 4: Fallback final - API pública de terceiro (exemplo) ---
    try:
        print(f"[Fallback API] Tentando: {youtube_url}")
        # Usa uma API gratuita de exemplo (pode não estar sempre disponível)
        response = requests.get(
            f"https://api.vevioz.com/api/button/mp3/{youtube_url}",
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("download_url"):
                mp3_resp = requests.get(data["download_url"], timeout=60)
                if mp3_resp.status_code == 200:
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                        tmp.write(mp3_resp.content)
                        return tmp.name, "Vevioz API"
        raise Exception("Resposta inválida da Vevioz")
    except Exception as e:
        print(f"[Fallback API] Falhou: {str(e)}")

    # Se tudo falhou
    return None, None

# ========== ENDPOINT PRINCIPAL ==========
@app.get("/download", response_model=DownloadResponse)
async def download_audio(url: str = Query(..., description="URL do YouTube")):
    """
    Endpoint que recebe a URL do YouTube, tenta baixar o áudio com fallback
    e retorna a URL pública do arquivo (ou erro).
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL não fornecida")

    file_path, method = download_audio_with_fallback(url)
    
    if file_path and os.path.exists(file_path):
        try:
            # Opção 1: Retornar o arquivo diretamente (útil para testes)
            # return FileResponse(file_path, media_type="audio/mpeg", filename=os.path.basename(file_path))
            
            # Opção 2: Fazer upload para um serviço de armazenamento (ex.: Cloudinary, Drive)
            # E retornar a URL pública. Exemplo simplificado:
            # uploaded_url = upload_to_cloudinary(file_path)
            # return DownloadResponse(success=True, audio_url=uploaded_url, fallback_used=method)
            
            # Por enquanto, retornamos apenas o caminho (para fins de demonstração)
            return DownloadResponse(
                success=True,
                audio_url=f"file://{file_path}",  # Na prática, substitua por URL pública
                fallback_used=method
            )
        except Exception as e:
            return DownloadResponse(success=False, error=f"Erro ao processar arquivo: {str(e)}")
        finally:
            # Limpeza opcional: agendar a exclusão do arquivo temporário após alguns minutos
            pass
    else:
        return DownloadResponse(
            success=False,
            error="Todas as estratégias de download falharam. Verifique a URL ou tente novamente mais tarde."
        )

# ========== ENDPOINT DE SAÚDE ==========
@app.get("/health")
async def health_check():
    return {"status": "ok", "temp_dir": TEMP_DIR}

# ========== EXECUÇÃO ==========
if __name__ == "__main__":
    # Certifique-se de que o ffmpeg está instalado no ambiente
    if not FFMPEG_PATH:
        print("⚠️  ffmpeg não encontrado! Instale com: apt-get install ffmpeg (Linux) ou brew install ffmpeg (Mac)")
    uvicorn.run(app, host="0.0.0.0", port=8000)