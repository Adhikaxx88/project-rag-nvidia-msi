"""
Konfigurasi terpusat, dibaca dari environment variables (.env).
Semua modul (ingestion, vectorization, llm, ui, orchestration) import dari sini
supaya tidak ada nilai hardcoded yang berbeda-beda di tiap file.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


# --- Data paths ---
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Ingestion ---
MIN_CONTENT_LENGTH = _int("MIN_CONTENT_LENGTH", 150)
MAX_ARTICLES_PER_TOPIC = _int("MAX_ARTICLES_PER_TOPIC", 8)
MAX_ARTICLE_AGE_DAYS = _int("MAX_ARTICLE_AGE_DAYS", 30)
REQUEST_DELAY_MIN_SECONDS = _float("REQUEST_DELAY_MIN_SECONDS", 1.0)
REQUEST_DELAY_MAX_SECONDS = _float("REQUEST_DELAY_MAX_SECONDS", 3.5)

# --- Vectorization / embedding ---
DENSE_MODEL_NAME = os.getenv("DENSE_MODEL_NAME", "BAAI/bge-large-en-v1.5")
SPARSE_MODEL_NAME = os.getenv("SPARSE_MODEL_NAME", "Qdrant/bm25")
# BGE adalah asymmetric embedding model: query butuh instruction prefix ini,
# passage/dokumen TIDAK perlu prefix (lihat model card BAAI/bge-large-en-v1.5).
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
CHUNK_SIZE = _int("CHUNK_SIZE", 512)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 64)

# --- Qdrant ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = _int("QDRANT_PORT", 6333)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "fed_news")

# --- Vectorization bridge service (native GPU host <-> Airflow container) ---
VECTOR_SERVICE_HOST = os.getenv("VECTOR_SERVICE_HOST", "0.0.0.0")
VECTOR_SERVICE_PORT = _int("VECTOR_SERVICE_PORT", 8600)
# URL yang dipanggil DARI DALAM container Airflow untuk mencapai service ini
# yang jalan native di host Windows. Docker Desktop menyediakan host.docker.internal.
VECTOR_SERVICE_URL = os.getenv("VECTOR_SERVICE_URL", "http://host.docker.internal:8600")

# --- Ollama / LLM ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
LLM_TOP_K = _int("LLM_TOP_K", 6)
