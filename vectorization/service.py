"""
Vectorization Bridge Service (FastAPI).

Kenapa service ini ada: di arsitektur "hybrid" project ini, Airflow jalan di
dalam Docker container (CPU only, tanpa akses GPU), sedangkan embedding BGE
butuh CUDA yang cuma tersedia native di host Windows. Jadi task "vectorize"
di Airflow DAG tidak menjalankan embedding secara langsung -- dia mengirim
HTTP request ke service ini (yang jalan native di host, lihat README) lewat
`host.docker.internal`, dan service inilah yang benar-benar menjalankan model
BGE + BM25 di GPU host lalu upsert ke Qdrant.

Jalankan (native, di venv host dengan CUDA):
    uvicorn vectorization.service:app --host 0.0.0.0 --port 8600
"""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
from fastapi import FastAPI
from pydantic import BaseModel

from vectorization.qdrant_store import ingest_articles

app = FastAPI(title="News RAG Vectorization Bridge Service")


class ArticleIn(BaseModel):
    title: str
    url: str
    content: str
    published: Optional[str] = None
    source: Optional[str] = None
    topic_category: Optional[str] = None
    search_query: Optional[str] = None


class VectorizeRequest(BaseModel):
    articles: list[ArticleIn]


@app.get("/health")
def health():
    return {"status": "ok", "cuda_available": torch.cuda.is_available()}


@app.post("/vectorize")
def vectorize(request: VectorizeRequest):
    articles = [a.model_dump() for a in request.articles]
    ingested_chunks = ingest_articles(articles)
    return {"articles_received": len(articles), "chunks_ingested": ingested_chunks}
