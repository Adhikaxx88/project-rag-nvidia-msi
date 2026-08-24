"""Sliding-window character chunking dengan overlap."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.settings import CHUNK_OVERLAP, CHUNK_SIZE


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Pecah `text` jadi list chunk ~chunk_size karakter, overlap antar chunk."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("overlap harus lebih kecil dari chunk_size")

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks
