"""
Airflow DAG: scrape (Google News RSS) -> clean -> vectorize (dense+sparse -> Qdrant).

Catatan arsitektur (lihat README): task `vectorize_news` TIDAK menjalankan
embedding di dalam container Airflow (container ini tidak punya akses GPU).
Task ini memanggil vectorization bridge service (FastAPI) yang jalan native
di host Windows dengan CUDA, lewat `host.docker.internal`. Jalankan service
itu (`uvicorn vectorization.service:app --port 8600`) SEBELUM DAG di-trigger,
kalau tidak task `vectorize_news` akan gagal dengan connection error yang jelas.
"""
import json
import sys
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path("/opt/airflow/project")
sys.path.insert(0, str(PROJECT_ROOT))

import pendulum
import requests
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "news-rag-pipeline",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def scrape_news(**context):
    from ingestion.scraper import fetch_news, save_articles

    articles = fetch_news()
    out_path = save_articles(articles, f"news_raw_{context['ds']}.json")
    return str(out_path)


def clean_news(**context):
    from ingestion.cleaner import clean_file

    raw_path = context["ti"].xcom_pull(task_ids="scrape_news")
    out_path = clean_file(Path(raw_path), f"news_clean_{context['ds']}.json")
    return str(out_path)


def vectorize_news(**context):
    from common.settings import VECTOR_SERVICE_URL

    cleaned_path = context["ti"].xcom_pull(task_ids="clean_news")
    with open(cleaned_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        return "Tidak ada artikel baru untuk divectorize."

    response = requests.post(
        f"{VECTOR_SERVICE_URL}/vectorize",
        json={"articles": articles},
        timeout=1800,
    )
    response.raise_for_status()
    return response.json()


with DAG(
    dag_id="news_rag_pipeline",
    description="Scrape Fed Reserve & global macro news -> clean -> vectorize into Qdrant hybrid RAG store.",
    default_args=default_args,
    schedule="0 */6 * * *",  # tiap 6 jam
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["news-rag", "fed-reserve", "macro"],
) as dag:
    scrape_task = PythonOperator(
        task_id="scrape_news",
        python_callable=scrape_news,
    )

    clean_task = PythonOperator(
        task_id="clean_news",
        python_callable=clean_news,
    )

    vectorize_task = PythonOperator(
        task_id="vectorize_news",
        python_callable=vectorize_news,
    )

    scrape_task >> clean_task >> vectorize_task
