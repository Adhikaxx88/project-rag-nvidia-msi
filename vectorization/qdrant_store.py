"""
Setup collection Qdrant (hybrid: dense "bge" + sparse "bm25") dan fungsi
untuk chunking + embedding + upsert artikel ke Qdrant.
"""
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from common.settings import COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT
from vectorization.chunker import chunk_text
from vectorization.embedder import encode_passages, encode_sparse, get_dense_dim

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"
UPSERT_BATCH_SIZE = 64

# Namespace tetap (fixed, jangan diubah) untuk uuid5 supaya point ID deterministic
# lintas run: url+chunk_index yang sama akan selalu hasilkan UUID yang sama persis,
# sehingga upsert() me-replace chunk lama alih-alih insert duplikat baru.
POINT_ID_NAMESPACE = uuid.UUID("a3f1c9e0-7b2d-4e6a-9c3f-1d8e5b6a2f4c")


def _build_point_id(url: str, chunk_index: int) -> str:
    return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{url}:{chunk_index}"))

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _client


def ensure_collection(client: QdrantClient | None = None) -> None:
    client = client or get_client()
    if client.collection_exists(COLLECTION_NAME):
        return

    dense_dim = get_dense_dim()
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={DENSE_VECTOR_NAME: VectorParams(size=dense_dim, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams(modifier=Modifier.IDF)},
    )
    logger.info("Collection '%s' dibuat (dense_dim=%d).", COLLECTION_NAME, dense_dim)


def _build_points(article: dict) -> list[PointStruct]:
    chunks = [c for c in chunk_text(article["content"]) if c.strip()]
    if not chunks:
        return []

    dense_vectors = encode_passages(chunks)
    sparse_vectors = encode_sparse(chunks)
    url = article.get("url")

    points = []
    for i, chunk in enumerate(chunks):
        sparse_vec = sparse_vectors[i]
        points.append(
            PointStruct(
                id=_build_point_id(url, i),
                vector={
                    DENSE_VECTOR_NAME: dense_vectors[i],
                    SPARSE_VECTOR_NAME: SparseVector(
                        indices=sparse_vec.indices.tolist(),
                        values=sparse_vec.values.tolist(),
                    ),
                },
                payload={
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "published": article.get("published"),
                    "source": article.get("source"),
                    "topic_category": article.get("topic_category"),
                    "chunk_index": i,
                    "chunk_text": chunk,
                },
            )
        )
    return points


def ingest_articles(articles: list[dict]) -> int:
    """Chunk + embed (dense & sparse) + upsert semua artikel ke Qdrant.

    Return jumlah chunk yang berhasil di-upsert.
    """
    client = get_client()
    ensure_collection(client)

    all_points: list[PointStruct] = []
    for article in articles:
        points = _build_points(article)
        if not points:
            logger.warning("Artikel tanpa konten valid untuk chunking: %s", article.get("url"))
            continue
        all_points.extend(points)

    for i in range(0, len(all_points), UPSERT_BATCH_SIZE):
        batch = all_points[i : i + UPSERT_BATCH_SIZE]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        logger.info("Upserted %d/%d chunks", i + len(batch), len(all_points))

    logger.info("Selesai: %d artikel -> %d chunk di-upsert ke '%s'.", len(articles), len(all_points), COLLECTION_NAME)
    return len(all_points)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Vectorize & ingest artikel JSON ke Qdrant.")
    parser.add_argument("json_path", help="Path ke file JSON hasil scraping/cleaning.")
    args = parser.parse_args()

    with open(args.json_path, "r", encoding="utf-8") as f:
        articles_ = json.load(f)
    ingest_articles(articles_)
