# Cara Kerja Sistem

Dokumen ini menjelaskan **logika/alur kerja** project ini secara menyeluruh — bukan cara
install (lihat `README.md` untuk itu), tapi **apa yang sebenarnya terjadi** di dalam sistem,
tahap demi tahap, dan file mana yang bertanggung jawab atas tiap tahap.

## 1. Overview singkat

Sistem ini punya dua fungsi yang berjalan **terpisah dan independen**: (1) secara berkala
(via Airflow) men-scrape berita Fed Reserve & macro global, membersihkannya, lalu menyimpannya
sebagai vector di Qdrant; dan (2) saat user bertanya lewat UI, mengambil potongan berita paling
relevan dari Qdrant lalu meminta LLM lokal (Ollama/Llama 3) menjawab **hanya** berdasarkan
potongan itu, lengkap dengan sitasi sumber dan klasifikasi sentimen Hawkish/Dovish/Neutral.
Kedua alur ini berbagi satu tempat penyimpanan (Qdrant), tapi tidak pernah berjalan
bersamaan dalam satu request — ingestion mengisi database, query membaca database.

## 2. Dua alur utama

Ini bagian paling penting untuk dipahami, karena keduanya sering tertukar: **Alur A hanya
perlu dijalankan sesekali** (saat ingin data berita baru), sedangkan **Alur B berjalan setiap
kali ada pertanyaan** dan sama sekali tidak bergantung pada Alur A sedang jalan atau tidak.

### Alur A — Ingestion (data masuk, otomatis via Airflow)

```
scrape_news  ─────────────▶  clean_news  ─────────────▶  vectorize_news
```

| Tahap | File / fungsi | Apa yang terjadi |
|---|---|---|
| `scrape_news` | `ingestion/scraper.py` (`fetch_news`) | Query Google News RSS untuk tiap topik di `ingestion/config.py` (Fed-specific & global macro), decode URL redirect Google, download & extract full text tiap artikel (`newspaper3k`), filter artikel < `MIN_CONTENT_LENGTH` karakter dan yang lebih tua dari `MAX_ARTICLE_AGE_DAYS`. Hasil disimpan sebagai JSON mentah di `data/raw/`. |
| `clean_news` | `ingestion/cleaner.py` (`clean_articles`) | Drop artikel dengan field wajib kosong (title/url/content), re-validasi panjang konten, dedupe berdasarkan URL & title, normalize whitespace berlebih. Hasil disimpan di `data/processed/`. |
| `vectorize_news` | `orchestration/dags/news_rag_pipeline_dag.py` → HTTP POST ke `vectorization/service.py` → `vectorization/qdrant_store.py` (`ingest_articles`) | Tiap artikel dipecah jadi beberapa chunk (`vectorization/chunker.py`, sliding window ~512 karakter + overlap 64), tiap chunk di-embed dua kali (dense BGE + sparse BM25, lihat `vectorization/embedder.py`), lalu di-upsert ke collection Qdrant `fed_news` dengan point ID deterministic (`uuid5` dari `url:chunk_index` — supaya re-scrape artikel yang sama meng-**replace**, bukan duplikat). |

**Kapan alur ini perlu dijalankan?** Hanya saat Anda ingin database berisi berita **baru**
(defaultnya otomatis tiap 6 jam lewat jadwal Airflow, `catchup=False`). **Tidak perlu**
dijalankan setiap kali user chat — chat (Alur B) hanya *membaca* apa yang sudah ada di Qdrant
dari ingestion run sebelumnya.

### Alur B — Query/Chat (user bertanya, real-time via UI)

```
user question ─▶ embed query (dense+sparse) ─▶ hybrid search Qdrant (RRF)
              ─▶ build context+sitasi ─▶ generate via Ollama ─▶ jawaban+sitasi ─▶ React UI
```

| Tahap | File / fungsi | Apa yang terjadi |
|---|---|---|
| Terima pertanyaan | `ui/frontend/src/App.tsx` → `POST /ask` → `ui/api.py` | User ketik pertanyaan di UI React, frontend `fetch('/ask', ...)` dengan `{question, top_k, topic_filter, model}`. `ui/api.py` menerima request dan memanggil `llm/rag_pipeline.py`. |
| Embed query | `vectorization/embedder.py` (`encode_query`, `encode_sparse`) | Pertanyaan user di-encode dua kali: dense (BGE, dengan instruction-prefix khusus untuk query — model asymmetric) dan sparse (BM25). |
| Hybrid search | `llm/retriever.py` (`hybrid_search`) | Kedua vector query dikirim ke Qdrant lewat satu `query_points` call dengan `Prefetch` dense + sparse, digabung pakai **RRF (Reciprocal Rank Fusion)** — hasilnya `top_k` chunk paling relevan (default 6), masing-masing membawa payload `title/url/published/source/chunk_text`. |
| Build context | `llm/prompts.py` (`build_context_and_sources`) | Chunk hasil retrieval di-dedupe by URL jadi daftar sumber bernomor `[1] [2] ...`, lalu dirangkai jadi satu blok teks context yang akan dibaca LLM. |
| Generate jawaban | `llm/generator.py` (`generate_answer`) → Ollama | `SYSTEM_PROMPT` (`llm/prompts.py`) + context block + pertanyaan dikirim ke Ollama (`llama3` default). System prompt secara eksplisit mewajibkan: jawab **hanya** dari excerpt yang diberikan, sitasi tiap klaim `[1]`/`[2]`, klasifikasi sentimen Hawkish/Dovish/Neutral kalau relevan. |
| Tampilkan | `ui/frontend/src/components/ResultEntry.tsx` + `SourceList.tsx` | Jawaban ditampilkan format "query → result" dengan kata sentimen di-highlight warna, daftar sumber (judul, source, tanggal) ditampilkan sebagai tabel citation yang bisa di-expand. |

**Poin paling penting: alur ini TIDAK butuh `vectorization/service.py` sama sekali.** Yang
dibutuhkan hanya tiga hal jalan bersamaan: **Qdrant** (baca data), **Ollama** (generate
jawaban), dan **`uvicorn ui.api:app`** (satu proses yang meng-handle embed query + hybrid
search + build context + panggil Ollama — semuanya di dalam proses Python yang sama, lewat
import langsung `llm/rag_pipeline.py` → `llm/retriever.py` → `vectorization/embedder.py`).
`vectorization/service.py` (port 8600) itu proses yang **terpisah total**, hanya dipanggil
oleh Airflow di Alur A saat ingest artikel baru — bukan bagian dari Alur B.

## 3. Diagram gabungan

```
                              ┌─────────────────────────────────┐
                              │            Qdrant                │
                              │   collection "fed_news" (Docker)  │
                              │   dense vector "bge" + sparse      │
                              │   vector "bm25" per chunk           │
                              │            [CPU-only]                │
                              └───────────▲──────────────▲─────────┘
                                          │ upsert       │ query (RRF)
                    ┌─────────────────────┘              └──────────────────────┐
                    │                                                            │
   ══════ ALUR A: INGESTION (jarang, terjadwal) ══════      ══════ ALUR B: QUERY/CHAT (tiap request) ══════
                    │                                                            │
   [Airflow, Docker, CPU-only]                                  [Native host, GPU/CUDA]
                    │                                                            │
   scrape_news (RSS)                                          user question
        │  ingestion/scraper.py                                    │  ui/frontend (React)
        ▼                                                          ▼
   clean_news                                                 POST /ask
        │  ingestion/cleaner.py                                    │  ui/api.py  (SATU proses)
        ▼                                                          ▼
   vectorize_news ──HTTP POST──▶ vectorization/service.py    embed query (BGE + BM25)
        │  (task Airflow)         (FastAPI :8600, native)         │  vectorization/embedder.py  [BGE: GPU]
        │                              │  GPU: BGE dense embed          ▼
        │                              │  CPU: BM25 sparse embed   hybrid search RRF
        │                              ▼                                │  llm/retriever.py  [CPU]
        │                        vectorization/qdrant_store.py          ▼
        │                        (chunk + embed + upsert)          build context + sitasi
        │                                                               │  llm/prompts.py
        └───────────────────────────────────────────────────┐          ▼
                                                              │     generate jawaban
                                                              │        │  llm/generator.py → Ollama  [GPU: VRAM]
                                                              │        ▼
                                                              │     jawaban + sitasi ──▶ React UI
                                                              │
                                              (kedua alur SAMA-SAMA baca/tulis Qdrant,
                                               tapi berjalan independen satu sama lain)
```

**Shared component:** hanya **Qdrant** — tempat Alur A menulis (upsert) dan Alur B membaca
(query). Semua komponen lain terpisah total antar alur:

| Komponen | Dipakai di alur | Docker atau native | GPU? |
|---|---|---|---|
| Airflow (webserver, scheduler) | A saja | Docker | Tidak (CPU-only, tidak ada akses GPU dari container) |
| `vectorization/service.py` (bridge, :8600) | A saja | Native (host) | Ya — BGE dense embed |
| Qdrant | A **dan** B (shared) | Docker | Tidak (CPU-only, murni vector search) |
| `ui/api.py` (:8502) | B saja | Native (host) | Ya — BGE dense embed (query) |
| Ollama | B saja (generation) | Native (host) | Ya — LLM generation (VRAM) |
| `ui/frontend` (React) | B saja | Native (build) → di-serve `ui/api.py` | Tidak |

## 4. Di mana persis GPU dipakai?

Cuma di **dua titik**, keduanya soal model neural network besar yang butuh akselerasi:

1. **Embedding dense BGE** (`vectorization/embedder.py`, model `BAAI/bge-large-en-v1.5` via
   `sentence-transformers`) — dipakai dua kali: saat ingest (encode tiap chunk artikel jadi
   passage vector, Alur A) dan saat query (encode pertanyaan user jadi query vector, Alur B).
   Fallback otomatis ke CPU kalau CUDA tidak terdeteksi (lebih lambat, tapi tetap jalan).
2. **Generation Ollama/Llama 3** (`llm/generator.py`) — model bahasa besar yang menyusun
   jawaban naratif, jalan di VRAM lewat `ollama serve`.

**Semua yang lain CPU-only**, tidak butuh dan tidak pakai GPU sama sekali:
- **BM25 sparse embedding** (`fastembed`) — algoritma keyword-statistik ringan, memang
  didesain untuk jalan di CPU.
- **Qdrant** — vector search engine-nya sendiri (baik dense maupun sparse search, termasuk
  RRF fusion) murni CPU, tidak butuh GPU untuk melakukan similarity search.
- **Airflow / orchestration** — scraping, cleaning, penjadwalan task — semua logic Python
  biasa, tidak ada komputasi neural network di sini.

## 5. FAQ

**Perlu jalankan `vectorization/service.py` untuk chat?**
Tidak. File itu hanya dipanggil Airflow (Alur A) saat ada artikel baru yang perlu di-embed
dan di-upsert ke Qdrant. Untuk chat (Alur B), file itu tidak pernah disentuh sama sekali —
lihat penjelasan di bagian Alur B di atas.

**File mana yang perlu dijalankan untuk sekadar chat?**
Cukup tiga hal: Qdrant jalan (`docker compose up -d`), Ollama jalan (`ollama serve`), dan
`uvicorn ui.api:app --port 8502`. Satu proses `ui.api:app` itu sudah meng-handle semuanya —
embed query, hybrid search, build context, panggil Ollama. Detail langkah lengkap ada di
`README.md` bagian "Quick start".

**Kenapa ada 2 model embedding (dense + sparse)?**
Karena keduanya menangkap jenis relevansi yang berbeda dan saling melengkapi. Dense (BGE)
bagus untuk relevansi **semantik/makna** — misalnya paham bahwa "menahan suku bunga" dan
"hold interest rate" berkaitan meski beda kata. Sparse (BM25) bagus untuk **kecocokan
kata kunci presisi** — misalnya angka spesifik ("5.25%"), nama ("Jerome Powell"), atau istilah
teknis yang harus persis cocok, yang kadang malah kurang ditangkap baik oleh model semantik.
Menggabungkan keduanya lewat RRF (`llm/retriever.py`) memberi hasil retrieval yang lebih
robust daripada pakai salah satu saja — ini yang disebut *hybrid search*.

**Data yang dijawab AI dari mana asalnya, apakah AI mengarang?**
Tidak. Jawaban LLM **hanya** boleh berasal dari potongan artikel berita yang sudah di-scrape
dan tersimpan di Qdrant (hasil Alur A) — bukan dari pengetahuan umum model. Ini ditegakkan
secara eksplisit di `SYSTEM_PROMPT` (`llm/prompts.py`): aturan #1 melarang LLM memakai
pengetahuan di luar excerpt yang diberikan atau mengarang fakta/angka/tanggal, dan aturan #2
mewajibkan tiap klaim faktual disertai sitasi `[1]`/`[2]` ke sumber excerpt-nya. Kalau tidak
ada berita relevan di Qdrant untuk suatu pertanyaan, sistem akan bilang begitu (lihat
`NO_RESULTS_MESSAGE` di `llm/rag_pipeline.py`) alih-alih menjawab dari "pengetahuan umum"
model — inilah inti dari pendekatan RAG (Retrieval-Augmented Generation) yang dipakai project
ini.
