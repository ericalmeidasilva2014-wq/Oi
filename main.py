import os
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from fastapi import FastAPI, HTTPException, Security, status, Depends
from fastapi.security import APIKeyHeader

app = FastAPI(title="Web Gateway API", version="1.0.0")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    expected_key = os.getenv("MY_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A variável de ambiente MY_API_KEY não foi configurada no servidor."
        )
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso não autorizado: cabeçalho X-API-Key inválido ou ausente."
        )
    return api_key

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
def search(q: str, _: str = Depends(verify_api_key)):
    if not q.strip():
        raise HTTPException(status_code=400, detail="O parâmetro de busca 'q' não pode ser vazio.")

    try:
        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(q, max_results=10):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", "")
                })
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao consultar o DuckDuckGo: {str(e)}"
        )

@app.get("/fetch")
def fetch_url(url: str, _: str = Depends(verify_api_key)):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL inválida. Deve iniciar com http:// ou https://.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
            tag.decompose()

        cleaned_text = " ".join(soup.stripped_strings)
        return {
            "url": url,
            "text": cleaned_text
        }

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout de 8 segundos excedido ao tentar acessar a URL."
        )
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=f"O servidor de destino respondeu com status {status_code}."
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha de conexão com a URL de destino: {str(e)}"
        )

