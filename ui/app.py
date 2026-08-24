"""
SUDAH TIDAK DIPAKAI -- diganti oleh ui/api.py (FastAPI + static/index.html).

File ini dipertahankan hanya sebagai referensi historis, BUKAN jalur aktif.
Jangan jalankan ini untuk demo/production.

Alasan diganti: model threading Streamlit (script jalan di background thread
terpisah) konflik dengan tamper-protection Norton 360 di sistem dev ini,
menyebabkan crash python.exe (Access Violation, WINHTTP.dll). FastAPI/uvicorn
jalan di main thread/event loop seperti vectorization/service.py, yang sudah
terbukti stabil di sistem yang sama. Detail lengkap ada di README.md bagian
"Jalankan UI (FastAPI)".

UI aktif sekarang:
    uvicorn ui.api:app --host 0.0.0.0 --port 8502

Dashboard Streamlit di bawah ini (chat interface untuk tanya-jawab Fed rate /
macro economy, retrieval Qdrant hybrid dense+BM25 RRF -> generation Ollama ->
jawaban + source citations) sudah 1:1 digantikan fungsinya oleh ui/api.py.
"""

import os

os.environ["NO_PROXY"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["HF_HUB_OFFLINE"] = "1"          # <- baru
os.environ["TRANSFORMERS_OFFLINE"] = "1"     # <- baru

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from common.settings import LLM_TOP_K, OLLAMA_MODEL
from llm.rag_pipeline import answer_question

st.set_page_config(page_title="Fed Rate & Macro News RAG", page_icon="📈", layout="wide")

TOPIC_OPTIONS = {
    "Semua topik": None,
    "Fed-specific (suku bunga, FOMC, Powell, CPI/PCE)": "fed_specific",
    "Global macro (ECB, China, oil, EM currency)": "global_macro",
}

with st.sidebar:
    st.header("⚙️ Pengaturan")
    topic_label = st.selectbox("Filter topik", list(TOPIC_OPTIONS.keys()))
    top_k = st.slider("Jumlah chunk konteks (top-k)", min_value=2, max_value=15, value=LLM_TOP_K)
    model_name = st.text_input("Ollama model", value=OLLAMA_MODEL)
    st.divider()
    st.caption(
        "Sistem ini hanya menjawab berdasarkan berita yang sudah di-ingest ke Qdrant "
        "lewat pipeline Airflow. Jawaban selalu menyertakan sitasi ke sumber berita asli."
    )
    if st.button("🗑️ Reset percakapan"):
        st.session_state.messages = []
        st.rerun()

st.title("📈 Fed Reserve Rate & Global Macro News — RAG Assistant")
st.caption(
    "Tanya soal keputusan suku bunga The Fed, FOMC, inflasi, atau kondisi makroekonomi global. "
    "Jawaban di-generate dari berita yang sudah diproses lewat Hybrid RAG (dense + BM25)."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander(f"📚 {len(message['sources'])} sumber berita"):
                for src in message["sources"]:
                    st.markdown(
                        f"**[{src['index']}] [{src['title']}]({src['url']})**  \n"
                        f"{src.get('source') or 'Unknown Source'} · {src.get('published') or 'tanggal tidak diketahui'}"
                    )

query = st.chat_input("Contoh: Apa keputusan suku bunga The Fed terbaru dan bagaimana sentimennya?")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Mencari berita relevan & generating jawaban..."):
            try:
                result = answer_question(
                    query,
                    top_k=top_k,
                    topic_filter=TOPIC_OPTIONS[topic_label],
                    model=model_name,
                )
            except Exception as exc:  # noqa: BLE001
                result = {
                    "answer": (
                        f"Terjadi error saat memproses pertanyaan: `{exc}`\n\n"
                        "Pastikan Qdrant sudah jalan (`docker compose ps`) dan Ollama sudah aktif "
                        f"dengan model `{model_name}` (`ollama pull {model_name}`)."
                    ),
                    "sources": [],
                }

        st.markdown(result["answer"])
        if result["sources"]:
            with st.expander(f"📚 {len(result['sources'])} sumber berita"):
                for src in result["sources"]:
                    st.markdown(
                        f"**[{src['index']}] [{src['title']}]({src['url']})**  \n"
                        f"{src.get('source') or 'Unknown Source'} · {src.get('published') or 'tanggal tidak diketahui'}"
                    )

    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
    )
