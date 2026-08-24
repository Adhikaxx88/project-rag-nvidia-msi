"""End-to-end RAG: hybrid retrieve -> build citation context -> generate via Ollama."""
import logging
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.settings import LLM_TOP_K, OLLAMA_MODEL
from llm.generator import generate_answer
from llm.prompts import build_context_and_sources
from llm.retriever import hybrid_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NO_RESULTS_MESSAGE = (
    "Maaf, tidak ditemukan berita relevan di database untuk menjawab pertanyaan ini. "
    "Coba jalankan ingestion pipeline lagi atau ubah kata kunci pertanyaan."
)

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def validate_citations(answer_text: str, sources: list[dict]) -> None:
    """Guardrail logging: cek apakah LLM mengarang nomor sitasi yang tidak ada di
    `sources`. Murni untuk debugging kualitas jawaban -- TIDAK mengubah `answer_text`
    atau mempengaruhi apa yang dikembalikan ke caller, cuma log warning kalau ada
    nomor sitasi [N] di jawaban yang di luar rentang sumber valid (1..len(sources)).
    """
    if not sources:
        return

    cited_numbers = {int(n) for n in _CITATION_PATTERN.findall(answer_text)}
    if not cited_numbers:
        return

    max_valid = len(sources)
    invalid_numbers = sorted(n for n in cited_numbers if n < 1 or n > max_valid)
    if invalid_numbers:
        logger.warning(
            "Sitasi tidak valid terdeteksi di jawaban LLM: %s (hanya ada %d sumber, "
            "rentang valid [1]-[%d]). Kemungkinan LLM mengarang nomor sitasi -- "
            "jawaban tetap dikembalikan apa adanya, ini cuma log untuk debugging.",
            invalid_numbers,
            max_valid,
            max_valid,
        )


def answer_question(
    query: str,
    top_k: int = LLM_TOP_K,
    topic_filter: Optional[str] = None,
    model: str = OLLAMA_MODEL,
) -> dict:
    hits = hybrid_search(query, top_k=top_k, topic_filter=topic_filter)
    if not hits:
        return {"answer": NO_RESULTS_MESSAGE, "sources": []}

    context_block, sources = build_context_and_sources(hits)
    answer = generate_answer(query, context_block, model=model)
    validate_citations(answer, sources)
    return {"answer": answer, "sources": sources}


if __name__ == "__main__":
    result = answer_question("Apa keputusan suku bunga The Fed terbaru dan bagaimana sentimennya?")
    print(result["answer"])
    print("\n--- Sumber ---")
    for src in result["sources"]:
        print(f"[{src['index']}] {src['title']} ({src['published']}) -> {src['url']}")
