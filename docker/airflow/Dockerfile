# Airflow image + dependency scraping (feedparser/newspaper3k/googlenewsdecoder).
# Sengaja TIDAK menginstall torch/sentence-transformers/fastembed di sini --
# embedding GPU dijalankan native di host lewat vectorization/service.py
# (lihat README bagian "Arsitektur Hybrid GPU").
FROM apache/airflow:2.11.2-python3.11

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir -r /requirements-airflow.txt