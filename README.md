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
ui/                  api.py (FastAPI, aktif) + static/index.html (frontend)
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
- Python 3.11 (native, di luar Docker) — untuk vectorization service, UI, dan
  testing manual.
- NVIDIA GPU + driver terpasang (untuk CUDA). Kalau CUDA tidak terdeteksi, semua
  script otomatis fallback ke CPU (lebih lambat, tapi tetap jalan).
- [Ollama for Windows](https://ollama.com/download) — LLM lokal.

## Setup dari nol

### 1. Clone & virtual environment

```powershell
cd project-rtx
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies (native venv)

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

### 4. Install & pull model Ollama

```powershell
ollama pull llama3
ollama serve   # biasanya sudah auto-run sebagai service setelah install
```

Cek jalan: `curl http://localhost:11434/api/tags` harus menampilkan `llama3`.

### 5. Jalankan Qdrant + Airflow (Docker)

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

### 6. Jalankan vectorization bridge service (native, GPU)

Di terminal terpisah (venv aktif), **wajib jalan sebelum trigger DAG**:

```powershell
uvicorn vectorization.service:app --host 0.0.0.0 --port 8600
```

Cek: `curl http://localhost:8600/health` → `{"status":"ok","cuda_available":true}`.

### 7. Jalankan DAG

Di Airflow UI, unpause & trigger DAG **`news_rag_pipeline`** (jadwal default: tiap 6
jam, `catchup=False`). DAG akan: scrape Google News → clean → POST ke vectorization
service → chunk+embed+upsert ke Qdrant.

Testing cepat tanpa Airflow (langsung dari venv, opsional):

```powershell
python -m ingestion.scraper
python -m ingestion.cleaner
python -m vectorization.qdrant_store data/processed/<nama_file_hasil_cleaner>.json
```

### 8. Jalankan UI (FastAPI)

```powershell
uvicorn ui.api:app --host 0.0.0.0 --port 8502
```

Buka http://localhost:8502, tanya soal Fed rate / macro economy — jawaban akan
menyertakan klasifikasi sentimen (kalau relevan) dan daftar sumber berita (judul,
link, tanggal terbit) di bawah tiap jawaban.

> UI ini dulunya Streamlit (`ui/app.py`), tapi diganti ke FastAPI + HTML/JS statis
> karena model threading Streamlit (script jalan di background thread terpisah)
> konflik dengan tamper-protection Norton 360 di sistem ini, menyebabkan crash
> `python.exe` (Access Violation, WINHTTP.dll). FastAPI/uvicorn jalan di
> main thread/event loop seperti `vectorization/service.py`, yang sudah terbukti
> stabil di sistem yang sama.
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
| UI (FastAPI)                  | 8502  |

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

- **`cuda_available: false`** di `/health` — cek `nvidia-smi` jalan, dan pastikan
  torch yang terinstall adalah build CUDA (`pip show torch` → cek versi ada `+cu`).
- **Task `vectorize_news` gagal connection error** — pastikan langkah 6 (bridge
  service) sudah jalan di host sebelum trigger DAG. `host.docker.internal` cuma
  reachable dari dalam container Docker Desktop, tidak perlu extra config di Windows.
- **`newspaper3k` error terkait `lxml.html.clean`** — pastikan `lxml_html_clean`
  ada di requirements (sudah ditambahkan), ini package terpisah sejak lxml 5.x.
- **Ollama model not found** — jalankan `ollama pull llama3` ulang, atau ganti
  `OLLAMA_MODEL` di `.env` / field model di sidebar UI ke model lain yang sudah di-pull.
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
