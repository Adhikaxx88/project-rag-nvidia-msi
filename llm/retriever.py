"""
Hybrid retrieval terhadap collection Qdrant: dense (semantic, paham konteks
Hawkish/Dovish) + sparse BM25 (keyword presisi, angka suku bunga) digabung
lewat RRF (Reciprocal Rank Fusion) via Qdrant Query API.
"""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    SparseVector,
)

from common.settings import COLLECTION_NAME, LLM_TOP_K
from vectorization.embedder import encode_query, encode_sparse
from vectorization.qdrant_store import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, get_client


def hybrid_search(query: str, top_k: int = LLM_TOP_K, topic_filter: Optional[str] = None) -> list[dict]:
    """Jalankan hybrid search (dense + BM25) dengan RRF fusion.

    Args:
        query: pertanyaan user.
        top_k: jumlah chunk relevan yang dikembalikan.
        topic_filter: optional, filter payload topic_category ("fed_specific" / "global_macro").

    Returns:
        List of dict {score, title, url, published, source, topic_category, chunk_text}.
    """
    client = get_client()

    dense_query = encode_query(query)
    sparse_query = encode_sparse([query])[0]

    query_filter = None
    if topic_filter:
        query_filter = Filter(
            must=[FieldCondition(key="topic_category", match=MatchValue(value=topic_filter))]
        )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=top_k * 2),
            Prefetch(
                query=SparseVector(
                    indices=sparse_query.indices.tolist(),
                    values=sparse_query.values.tolist(),
                ),
                using=SPARSE_VECTOR_NAME,
                limit=top_k * 2,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    return [
        {
            "score": point.score,
            "title": point.payload.get("title"),
            "url": point.payload.get("url"),
            "published": point.payload.get("published"),
            "source": point.payload.get("source"),
            "topic_category": point.payload.get("topic_category"),
            "chunk_text": point.payload.get("chunk_text"),
        }
        for point in results.points
    ]
