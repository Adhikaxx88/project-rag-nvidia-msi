# Automated News RAG Pipeline — Fed Reserve Rate & Global Macro

Pipeline otomatis: scraping berita Google News (Fed Reserve + macroeconomic global) →
cleaning → **Hybrid RAG** (dense BGE + sparse BM25, RRF fusion) di Qdrant → jawaban
via LLM lokal (Ollama/Llama 3) yang selalu menyertakan sitasi sumber berita asli dan
klasifikasi sentimen Hawkish/Dovish/Neutral.

## Arsitektur

Project ini pakai arsitektur **hybrid**: orkestrasi (Airflow) & vector DB (Qdrant)
jalan di Docker (CPU-only, tidak butuh setup NVIDIA Container Toolkit yang rewel di
Windows), sementara semua yang butuh **GPU/CUDA** (embedding BGE, generation Ollama,
query embedding di UI) jalan **native** di host Windows supaya langsung pakai
CUDA driver yang sudah terpasang.

```
[Airflow (Docker)]                         [Host Windows, native, GPU/CUDA]
 scrape_news (RSS)                          ollama serve (llama3, VRAM)
   -> clean_news                            vectorization/service.py (FastAPI :8600)
     -> vectorize_news ---HTTP POST--->       -> BGE embed + BM25 + upsert
                                                                |
                                                                v
                                                     [Qdrant (Docker) :6333]
                                                                ^
                                                                |
                                          ui/api.py (FastAPI, native) <--- user
                                          (query embed CUDA -> hybrid search RRF
                                           -> Ollama generate -> jawaban + sitasi)
```

Task `vectorize_news` di Airflow **tidak** menjalankan embedding di dalam container
(container tidak punya akses GPU) — dia HTTP POST ke `vectorization/service.py` yang
harus sudah jalan native di host (lihat langkah 5 di bawah). Ini konsekuensi langsung
dari keputusan arsitektur "Hybrid" yang sudah dikonfirmasi sebelumnya.

## Struktur folder

```
common/            settings.py — semua config baca dari .env
ingestion/          config.py (topik+UA), scraper.py, cleaner.py
vectorization/       chunker.py, embedder.py (BGE+BM25), qdrant_store.py, service.py (bridge)
llm/                 retriever.py (hybrid RRF), prompts.py, generator.py (Ollama), rag_pipeline.py
orchestration/dags/  news_rag_pipeline_dag.py (Airflow DAG)
ui/                  api.py (FastAPI, aktif — serve /ask + hasil build frontend)
                     frontend/  React + TypeScript + Vite (source UI aktif)
                     app.py — LEGACY, sudah tidak dipakai (lihat catatan migrasi di bawah)
docker/
  airflow/           Dockerfile, requirements-airflow.txt, docker-compose.yml (modular)
  qdrant/            docker-compose.yml (modular)
docker-compose.yml   gabungan: Qdrant + Postgres + Airflow (webserver/scheduler/init)
data/raw/            output scraper (JSON mentah)
data/processed/      output cleaner (JSON setelah cleaning, siap divectorize)
```

## Prasyarat

- Windows 10/11 + Docker Desktop (WSL2 backend) — untuk Qdrant & Airflow.
- Python 3.11 (native, di luar Docker) — untuk vectorization service, UI backend, dan
  testing manual. Environment manager bebas (`venv` atau `conda`) — contoh di README ini
  pakai `venv`; kalau pakai conda, ganti langkah aktivasi environment dengan
  `conda activate <nama-env-anda>` (mis. `rtx-news-rag`).
- NVIDIA GPU + driver terpasang (untuk CUDA). Kalau CUDA tidak terdeteksi, semua
  script otomatis fallback ke CPU (lebih lambat, tapi tetap jalan).
- [Ollama for Windows](https://ollama.com/download) — LLM lokal.
- **Node.js 18+** (disarankan versi LTS terbaru) + npm — untuk build frontend
  React di `ui/frontend/`. Cek versi: `node --version`.

## Setup dari nol

Langkah-langkah ini **satu kali saja** (atau tiap kali dependency/kode berubah) —
bukan yang dijalankan tiap mau pakai. Untuk urutan menjalankan sehari-hari, lihat
bagian [Cara menjalankan](#cara-menjalankan) di bawah.

### 1. Clone & virtual environment

```powershell
cd project-rtx
python -m venv .venv
.venv\Scripts\activate
```

> Pakai conda? `conda create -n rtx-news-rag python=3.11` lalu
> `conda activate rtx-news-rag`, lanjutkan langkah 2 seperti biasa (environment
> manager tidak mempengaruhi langkah-langkah setelah ini).

### 2. Install dependencies (native venv/conda)

Install PyTorch versi CUDA **dulu** (sesuaikan `cu121` dengan versi CUDA driver
Anda, cek di [pytorch.org](https://pytorch.org/get-started/locally/)):

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

Verifikasi CUDA terdeteksi:

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### 3. Konfigurasi environment

```powershell
copy .env.example .env
```

Default sudah siap pakai untuk setup lokal Windows; edit kalau port bentrok dengan
service lain di mesin Anda.

### 4. Install model Ollama

```powershell
ollama pull llama3
```

(Ini cuma download model sekali — menjalankan Ollama server-nya ada di bagian
"Cara menjalankan" di bawah, karena itu perlu dilakukan tiap sesi, bukan sekali saja.)

### 5. Build frontend (React + TypeScript + Vite)

```powershell
cd ui/frontend
npm install
npm run build
cd ../..
```

Hasil build ada di `ui/frontend/dist/` — inilah yang di-serve `ui/api.py` di route
`/`. Ulangi `npm run build` tiap kali Anda mengubah kode di `ui/frontend/src/`.

## Cara menjalankan

Ada **dua alur terpisah**, tergantung tujuan Anda:

- **Quick start** — kalau cuma mau **tanya-jawab** lewat UI (kasus paling umum,
  termasuk demo). Tidak perlu Airflow, tidak perlu bridge service.
- **Full setup** — kalau mau **scraping berita baru** ke Qdrant (lewat Airflow DAG
  terjadwal atau manual). Butuh semua service.

> **Poin penting yang sempat bikin bingung saat development:** proses
> `uvicorn ui.api:app` **sendirian** sudah otomatis meng-handle loading dense model
> (BGE, jalan di GPU kalau ada CUDA), sparse model (BM25, CPU), koneksi ke Qdrant,
> DAN koneksi ke Ollama — semua di dalam satu proses Python yang sama (lihat
> `llm/retriever.py` dan `vectorization/embedder.py`, yang di-import langsung oleh
> `ui/api.py` lewat `llm/rag_pipeline.py`). **Anda TIDAK perlu menjalankan
> `vectorization/service.py` untuk sekadar chat/tanya-jawab.** File itu
> (`vectorization/service.py`, port 8600) HANYA dipakai sebagai *bridge* saat
> Airflow container melakukan scraping+vectorize artikel baru (task `vectorize_news`
> di DAG) — di luar konteks itu, file tersebut tidak perlu jalan sama sekali.

### A. Quick start — tanya-jawab saja

Prasyarat: langkah "Setup dari nol" di atas sudah pernah dilakukan (dependency
terinstall, `.env` ada, model Ollama sudah di-pull, frontend sudah di-build).

**1. Pastikan Qdrant jalan.** Kalau belum pernah setup sama sekali:

```powershell
docker compose up -d
```

Kalau Qdrant sudah pernah di-setup dan cuma perlu start ulang container yang sudah
ada (lebih cepat, tidak perlu `--build`), atau Anda hanya butuh Qdrant tanpa
Airflow sama sekali:

```powershell
docker compose -f docker/qdrant/docker-compose.yml up -d
```

**2. Pastikan Ollama jalan.**

```powershell
curl http://localhost:11434/api/tags
```

Kalau responnya gagal connect (`curl: (7) Failed to connect`), Ollama belum
jalan — buka terminal terpisah, jalankan, dan **biarkan tetap terbuka**:

```powershell
ollama serve
```

Ulangi `curl` di atas sampai muncul daftar model termasuk `llama3`.

**3. Aktifkan environment Python, lalu jalankan backend UI.**

```powershell
.venv\Scripts\activate
:: atau kalau pakai conda: conda activate rtx-news-rag

uvicorn ui.api:app --host 0.0.0.0 --port 8502
```

**4. Buka http://localhost:8502** — tanya soal Fed rate / macro economy. Selesai;
tidak ada langkah lain yang diperlukan untuk alur ini.

### B. Full setup — scraping berita baru

Butuh semua service: Qdrant, Airflow, DAN vectorization bridge service (beda dari
alur A di atas, karena di sini embedding artikel baru dilakukan lewat Airflow yang
jalan di container tanpa akses GPU — lihat diagram di bagian Arsitektur).

**1. Jalankan Qdrant + Airflow (Docker)**

```powershell
docker compose up -d --build
```

Ini menjalankan: `qdrant` (localhost:6333), `postgres` (metadata Airflow),
`airflow-init` (migrate DB + buat user admin, jalan sekali lalu exit),
`airflow-webserver` (localhost:8081), `airflow-scheduler`.

Login Airflow UI di http://localhost:8081 dengan **admin / admin**.

> Mau jalankan modular (terpisah)? `docker compose -f docker/qdrant/docker-compose.yml up -d`
> dan `docker compose -f docker/airflow/docker-compose.yml up -d --build` — keduanya
> independen, tidak saling bergantung secara network.

**2. Jalankan vectorization bridge service (native, GPU)**

Di terminal terpisah (venv/conda aktif), **wajib jalan sebelum trigger DAG** — ini
yang membedakan alur ini dari Quick Start di atas:

```powershell
uvicorn vectorization.service:app --host 0.0.0.0 --port 8600
```

Cek: `curl http://localhost:8600/health` → `{"status":"ok","cuda_available":true}`.

**3. Jalankan DAG**

Di Airflow UI, unpause & trigger DAG **`news_rag_pipeline`** (jadwal default: tiap 6
jam, `catchup=False`). DAG akan: scrape Google News → clean → POST ke vectorization
service → chunk+embed+upsert ke Qdrant.

Testing cepat tanpa Airflow (langsung dari venv, opsional):

```powershell
python -m ingestion.scraper
python -m ingestion.cleaner
python -m vectorization.qdrant_store data/processed/<nama_file_hasil_cleaner>.json
```

Setelah artikel baru masuk ke Qdrant, kembali ke alur **Quick start (A)** di atas
untuk tanya-jawab menggunakan data terbaru — bridge service (`vectorization/service.py`)
boleh dimatikan lagi setelah ingestion selesai, tidak perlu terus jalan.

### Development frontend (hot-reload)

Kalau mau edit UI React dan lihat perubahannya langsung tanpa `npm run build`
berulang kali, jalankan di dua terminal terpisah:

```powershell
# Terminal A -- backend (sama seperti Quick start langkah 3)
uvicorn ui.api:app --host 0.0.0.0 --port 8502

# Terminal B -- frontend dev server (hot reload)
cd ui/frontend
npm run dev
```

Buka http://localhost:5173 (Vite dev server) selama development — bukan :8502.
`vite.config.ts` sudah dikonfigurasi supaya request `/ask` dari dev server
di-proxy otomatis ke backend `:8502`, jadi tidak ada masalah CORS. Setelah
selesai edit, `npm run build` lagi supaya `:8502` (mode production) ikut update.

> UI ini dulunya Streamlit (`ui/app.py`), lalu sempat jadi HTML/JS statis polos
> (`ui/static/`, sudah dihapus setelah migrasi ke React), sekarang React + TypeScript
> + Vite. Streamlit diganti karena model threading-nya (script jalan di background
> thread terpisah) konflik dengan tamper-protection Norton 360 di sistem ini,
> menyebabkan crash `python.exe` (Access Violation, WINHTTP.dll). FastAPI/uvicorn
> jalan di main thread/event loop seperti `vectorization/service.py`, yang sudah
> terbukti stabil di sistem yang sama — keputusan itu tidak berubah, cuma
> frontend-nya yang di-upgrade dari HTML/JS statis ke React+TS untuk desain yang
> lebih matang.
>
> `ui/app.py` **tidak dihapus** (disimpan sebagai referensi historis dan bagian
> dari cerita migrasi teknis), tapi sudah ditandai jelas di docstring-nya sebagai
> tidak aktif dan tidak boleh dijalankan — dependency `streamlit` juga sudah
> dilepas dari `requirements.txt`, jadi `ui/app.py` **tidak akan bisa dijalankan**
> tanpa install ulang `streamlit` secara manual.

## Port default

| Service                     | Port  |
|------------------------------|-------|
| Qdrant REST                  | 6333  |
| Qdrant gRPC                  | 6334  |
| Airflow Webserver             | 8081  |
| Vectorization bridge (FastAPI)| 8600  |
| Ollama                        | 11434 |
| UI (FastAPI, production/demo) | 8502  |
| UI frontend dev server (Vite, opsional) | 5173 |

## Scraping: seleksi artikel per topic

`ingestion/scraper.py` (`fetch_news`) memilih artikel mana yang di-scrape per topic
dengan pendekatan **filter by date range**, bukan sekadar limit by count:

1. Semua entry RSS per query di-sort by `published_parsed` (terbaru dulu).
2. Entry di-filter: hanya yang terbit dalam **`MAX_ARTICLE_AGE_DAYS` hari terakhir**
   (default **30 hari**) yang diproses lebih lanjut (decode URL, download, extract).
   Entry tanpa `published_parsed` (tanggal tidak diketahui) tetap diproses — lebih
   aman diproses daripada berisiko kehilangan artikel valid.
3. `MAX_ARTICLES_PER_TOPIC` (default 8) tetap berlaku sebagai **safety cap**: kalau
   dalam rentang tanggal itu ada banyak entry, tetap dibatasi jumlah maksimalnya
   (diambil yang terbaru dulu). Tapi kalau dalam 30 hari cuma ada, misalnya, 5
   entry yang lolos filter tanggal, ya cuma 5 itu yang diproses — tidak dipaksa
   mundur ke entry yang lebih lama dari 30 hari demi mengejar angka cap.
4. Log per query menampilkan jumlah entry yang lolos vs. di-skip karena kelewat lama.

Untuk mengubah rentang tanggal (misal jadi 7 hari atau 60 hari), set
`MAX_ARTICLE_AGE_DAYS` di `.env` (lihat `.env.example`):

```
MAX_ARTICLE_AGE_DAYS=7
```

Atau override langsung lewat parameter kalau memanggil `fetch_news()` sebagai fungsi:

```python
from ingestion.scraper import fetch_news
articles = fetch_news(max_age_days=7)
```

## Persistensi data & idempotensi

Pipeline ini didesain supaya aman di-run berulang kali (tiap 6 jam via DAG, atau
manual) tanpa numpuk duplikat, di dua level:

- **Qdrant (`vectorization/qdrant_store.py`)** — point ID dibuat deterministic
  lewat `uuid.uuid5(POINT_ID_NAMESPACE, f"{url}:{chunk_index}")`, bukan
  `uuid.uuid4()` random. Artinya artikel dengan `url` yang sama, kalau di-scrape
  ulang di run berikutnya, akan menghasilkan point ID persis sama untuk tiap
  chunk-nya — `client.upsert()` jadi **replace** chunk lama, bukan insert baru.
  Jumlah point di collection tidak terus bertambah untuk artikel yang berulang.
- **File JSON hasil scraping (`ingestion/scraper.py: save_articles`)** — kalau
  file output yang dituju sudah ada, isinya dibaca dulu, artikel baru di-append
  (dedup by `url`, artikel yang URL-nya sudah ada di-skip), lalu ditulis ulang
  sebagai satu file gabungan. Ini membuat file JSON dengan nama tetap (misal
  dipanggil manual berkali-kali dengan nama yang sama) berfungsi sebagai histori
  akumulatif, bukan ketimpa total tiap run.

Catatan soal DAG: `scrape_news`/`clean_news` di `orchestration/dags/news_rag_pipeline_dag.py`
menulis file **per-tanggal** (`news_raw_{ds}.json`, `news_clean_{ds}.json`, `ds` =
tanggal eksekusi run), dan task berikutnya (`clean_news`, `vectorize_news`) selalu
membaca lewat XCom path spesifik yang dikembalikan task sebelumnya — bukan file
histori gabungan. Jadi `vectorize_news` per run **hanya** memproses artikel dari
file hari itu saja; ini sudah otomatis mencegah re-vectorize artikel lama tanpa
perlu logic tambahan di DAG, dan sejalan dengan fix idempotensi Qdrant di atas
(kalaupun ada artikel yang somehow ke-vectorize dua kali, upsert akan replace, bukan
duplikat).

## Troubleshooting

- **`Ollama connection refused` / `Failed to connect to Ollama`** saat tanya di UI —
  Ollama kadang **tidak auto-start** lagi setelah laptop di-restart (meskipun
  terinstall sebagai service). Cek dulu: `curl http://localhost:11434/api/tags`.
  Kalau gagal connect, jalankan `ollama serve` manual di terminal terpisah dan
  **biarkan terminal itu tetap terbuka** selama Anda pakai UI, lalu ulangi `curl`
  di atas sampai berhasil sebelum mencoba tanya lagi di UI. Lihat juga bagian
  [Quick start](#a-quick-start--tanya-jawab-saja) langkah 2.
- **`Could not load model Qdrant/bm25 from any source`** saat tanya di UI — ini
  **bukan** berarti modelnya belum pernah ter-download. Root cause: fastembed
  (library yang load model sparse/BM25) untuk model `Qdrant/bm25` **tidak mengecek
  cache lokal dulu** sebelum mencoba network call ke HuggingFace Hub (ini
  keterbatasan/bug di fastembed sendiri, bukan di kode project ini) — jadi koneksi
  internet tetap dibutuhkan minimal untuk metadata check di setiap proses baru,
  **walaupun model sudah pernah di-download dan ter-cache sebelumnya**. Kalau
  environment variable `HF_HUB_OFFLINE=1` di-set, network call metadata itu
  diblokir total → load gagal → muncul error generik ini, terlepas dari cache ada
  atau tidak. Fix-nya: **jangan set `HF_HUB_OFFLINE=1`**. Ini sudah diperbaiki di
  `ui/api.py` (dan `ui/app.py` legacy) — baris itu sudah dihapus. Kalau error ini
  muncul lagi: (a) pastikan Anda tidak menambahkan kembali `HF_HUB_OFFLINE=1` /
  `TRANSFORMERS_OFFLINE=1` di kode atau di `.env`, dan (b) pastikan ada koneksi
  internet aktif saat `uvicorn ui.api:app` pertama kali start di sesi itu.
- **`cuda_available: false`** di `/health` — cek `nvidia-smi` jalan, dan pastikan
  torch yang terinstall adalah build CUDA (`pip show torch` → cek versi ada `+cu`).
- **Task `vectorize_news` gagal connection error** — pastikan vectorization bridge
  service (`uvicorn vectorization.service:app --port 8600`, lihat
  [Full setup langkah 2](#b-full-setup--scraping-berita-baru)) sudah jalan di host
  sebelum trigger DAG. `host.docker.internal` cuma reachable dari dalam container
  Docker Desktop, tidak perlu extra config di Windows.
- **`newspaper3k` error terkait `lxml.html.clean`** — pastikan `lxml_html_clean`
  ada di requirements (sudah ditambahkan), ini package terpisah sejak lxml 5.x.
- **Ollama model not found** — jalankan `ollama pull llama3` ulang, atau ganti
  `OLLAMA_MODEL` di `.env` / field model di sidebar UI ke model lain yang sudah di-pull.
- **Buka `http://localhost:8502` tapi dapat 404 / halaman kosong** — frontend belum
  di-build. Jalankan `npm install && npm run build` di `ui/frontend/` (lihat bagian
  Setup dari nol langkah 5), lalu restart/reload `:8502`. Endpoint `/ask` sendiri
  tetap jalan walau frontend belum di-build (dicek langsung lewat `curl`/Postman
  kalau perlu debug backend saja).
- **Port bentrok** — ubah mapping port di `docker-compose.yml` / `.env`.

## Asumsi teknis (sudah dikonfirmasi)

- **GPU strategy**: hybrid native+Docker (bukan full Docker GPU passthrough) — lihat
  bagian Arsitektur di atas.
- **Airflow**: versi **2.11.2** (dicek Agustus 2026 — ini rilis terakhir jalur 2.x,
  sudah berstatus deprecated karena Airflow 3.x sekarang jadi versi stable utama;
  dipilih tetap karena pola docker-compose `LocalExecutor` jauh lebih matang/battle-
  tested untuk single-machine/dev dan DAG `PythonOperator` yang dipakai di sini
  kompatibel tanpa perubahan). Kalau nanti mau migrasi ke Airflow 3.x, komponen
  `airflow-webserver` perlu diganti jadi `airflow-api-server` dan beberapa env var
  auth manager berubah -- DAG Python-nya sendiri kemungkinan besar tetap kompatibel.
- **Target deploy**: Windows lokal dengan GPU NVIDIA sudah siap; fallback otomatis
  ke CPU kalau CUDA tidak terdeteksi.
- Kalau nanti mau pindah ke server Linux dengan GPU, `docker/airflow/Dockerfile` bisa
  diperluas untuk include `torch`+`sentence-transformers`+`fastembed` dan
  `docker-compose.yml` ditambah `deploy.resources.reservations.devices` (NVIDIA
  runtime) supaya vectorization berjalan penuh di dalam container — bridge service
  di langkah 6 jadi tidak diperlukan lagi.
