"""
Wrapper untuk dense embedding (BGE via Sentence-Transformers, GPU/CUDA) dan
sparse embedding (BM25 via FastEmbed). Model dimuat sekali (singleton) supaya
tidak reload tiap panggilan.

PENTING (asymmetric embedding BGE):
  - Passage/dokumen: encode_passages() -> TIDAK ada prefix.
  - Query: encode_query() -> otomatis di-prefix dengan instruction string
    "Represent this sentence for searching relevant passages: ".
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
from fastembed import SparseTextEmbedding
from sentence_transformers import SentenceTransformer

from common.settings import BGE_QUERY_INSTRUCTION, DENSE_MODEL_NAME, SPARSE_MODEL_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

_dense_model: SentenceTransformer | None = None
_sparse_model: SparseTextEmbedding | None = None


def get_device() -> str:
    return DEVICE


def _load_dense() -> SentenceTransformer:
    global _dense_model
    if _dense_model is None:
        logger.info("Loading dense model '%s' on %s...", DENSE_MODEL_NAME, DEVICE)
        if DEVICE == "cpu":
            logger.warning(
                "CUDA tidak terdeteksi, embedding jalan di CPU (jauh lebih lambat). "
                "Cek instalasi PyTorch CUDA build & NVIDIA driver kalau ini tidak diharapkan."
            )
        _dense_model = SentenceTransformer(DENSE_MODEL_NAME, device=DEVICE)
    return _dense_model


def _load_sparse() -> SparseTextEmbedding:
    global _sparse_model
    if _sparse_model is None:
        logger.info("Loading sparse (BM25) model '%s'...", SPARSE_MODEL_NAME)
        _sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    return _sparse_model


def get_dense_dim() -> int:
    return _load_dense().get_sentence_embedding_dimension()


def encode_passages(texts: list[str]) -> list[list[float]]:
    """Dense-encode dokumen/passage. Tidak pakai instruction prefix."""
    model = _load_dense()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def encode_query(query: str) -> list[float]:
    """Dense-encode query. WAJIB pakai instruction prefix (asymmetric model)."""
    model = _load_dense()
    vector = model.encode(BGE_QUERY_INSTRUCTION + query, normalize_embeddings=True)
    return vector.tolist()


def encode_sparse(texts: list[str]):
    """BM25 sparse-encode (dipakai sama untuk passage maupun query, symmetric)."""
    model = _load_sparse()
    return list(model.embed(texts))
