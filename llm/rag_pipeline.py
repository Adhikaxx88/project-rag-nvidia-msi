"""End-to-end RAG: hybrid retrieve -> build citation context -> generate via Ollama."""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.settings import LLM_TOP_K, OLLAMA_MODEL
from llm.generator import generate_answer
from llm.prompts import build_context_and_sources
from llm.retriever import hybrid_search

NO_RESULTS_MESSAGE = (
    "Maaf, tidak ditemukan berita relevan di database untuk menjawab pertanyaan ini. "
    "Coba jalankan ingestion pipeline lagi atau ubah kata kunci pertanyaan."
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
    return {"answer": answer, "sources": sources}


if __name__ == "__main__":
    result = answer_question("Apa keputusan suku bunga The Fed terbaru dan bagaimana sentimennya?")
    print(result["answer"])
    print("\n--- Sumber ---")
    for src in result["sources"]:
        print(f"[{src['index']}] {src['title']} ({src['published']}) -> {src['url']}")
