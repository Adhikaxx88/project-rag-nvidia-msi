"""
FastAPI UI backend: endpoint /ask untuk tanya-jawab Fed rate / macro economy.
Retrieval dari Qdrant (hybrid dense+BM25 RRF) -> generation via Ollama ->
jawaban + source citations (title, url, published date).

Frontend (React + TypeScript + Vite) ada di ui/frontend/. Backend ini men-serve
hasil build production-nya (ui/frontend/dist/) sebagai static files -- lihat
README.md bagian "Jalankan UI" untuk alur build & dev server.

Sebelumnya UI ini pernah pakai Streamlit (ui/app.py, sudah tidak dipakai) lalu
HTML/JS statis polos (ui/static/, sudah dihapus setelah migrasi ke React).
Streamlit diganti karena background-thread model-nya konflik dengan
tamper-protection Norton 360 di sistem dev ini (Access Violation di
WINHTTP.dll) -- FastAPI/uvicorn jalan di main thread/event loop dan terbukti
stabil.

Jalankan (native, di venv host), setelah build frontend (lihat README):
    uvicorn ui.api:app --host 0.0.0.0 --port 8502
"""

import os

os.environ["NO_PROXY"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from common.settings import LLM_TOP_K, OLLAMA_MODEL
from llm.rag_pipeline import answer_question

# Hasil `npm run build` di ui/frontend/ (lihat README). Tidak di-generate di sini --
# harus di-build manual dulu sebelum menjalankan service ini di mode production.
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

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


# Mount di paling akhir (setelah /ask) supaya route API tidak "ketutup" oleh
# static file serving. html=True: request ke "/" otomatis serve index.html.
# Kalau folder ini belum ada, jalankan `npm run build` dulu di ui/frontend/
# (lihat README bagian "Jalankan UI") -- development interaktif pakai
# `npm run dev` di ui/frontend/ (Vite dev server di :5173) alih-alih ini.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    import logging

    logging.getLogger(__name__).warning(
        "Frontend build tidak ditemukan di %s -- jalankan `npm run build` di "
        "ui/frontend/ dulu, atau pakai `npm run dev` untuk development. "
        "Endpoint /ask tetap aktif tanpa UI.",
        FRONTEND_DIST,
    )
