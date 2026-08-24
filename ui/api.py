"""
FastAPI UI: chat interface untuk tanya-jawab Fed rate / macro economy.
Retrieval dari Qdrant (hybrid dense+BM25 RRF) -> generation via Ollama ->
jawaban + source citations (title, url, published date).

Menggantikan ui/app.py (Streamlit) karena Streamlit menjalankan script di
background thread terpisah, yang konflik dengan tamper-protection Norton 360
di sistem ini (Access Violation di WINHTTP.dll). FastAPI/uvicorn menjalankan
semuanya di main thread/event loop, sama seperti vectorization/service.py
yang sudah terbukti stabil di sistem yang sama.

Jalankan (native, di venv host):
    uvicorn ui.api:app --host 0.0.0.0 --port 8502
"""

import os

os.environ["NO_PROXY"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from common.settings import LLM_TOP_K, OLLAMA_MODEL
from llm.rag_pipeline import answer_question

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Fed Rate & Macro News RAG UI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    top_k: int = LLM_TOP_K
    topic_filter: Optional[str] = None
    model: str = OLLAMA_MODEL


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/ask")
def ask(request: AskRequest):
    try:
        return answer_question(
            request.question,
            top_k=request.top_k,
            topic_filter=request.topic_filter,
            model=request.model,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "answer": (
                f"Terjadi error saat memproses pertanyaan: `{exc}`\n\n"
                "Pastikan Qdrant sudah jalan (`docker compose ps`) dan Ollama sudah aktif "
                f"dengan model `{request.model}` (`ollama pull {request.model}`)."
            ),
            "sources": [],
        }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
