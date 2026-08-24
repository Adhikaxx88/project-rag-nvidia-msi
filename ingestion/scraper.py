"""
Scraper berita Google News RSS untuk topik Fed Reserve & macroeconomic global.

Pipeline per artikel:
  1. Parse RSS feed (feedparser) dengan User-Agent random.
  2. Decode redirect URL Google News jadi URL artikel asli (googlenewsdecoder).
  3. Extract judul + full text (newspaper3k) dengan User-Agent random.
  4. Skip kalau konten < MIN_CONTENT_LENGTH karakter.
  5. Delay random (bukan fixed) antar request supaya sopan ke server sumber.

Bisa dijalankan standalone:
    python -m ingestion.scraper
atau dipanggil sebagai fungsi dari Airflow DAG / script lain via fetch_news().
"""
import calendar
import json
import logging
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser
from googlenewsdecoder import gnewsdecoder
from newspaper import Article

from common.settings import (
    MAX_ARTICLE_AGE_DAYS,
    MAX_ARTICLES_PER_TOPIC,
    MIN_CONTENT_LENGTH,
    RAW_DATA_DIR,
    REQUEST_DELAY_MAX_SECONDS,
    REQUEST_DELAY_MIN_SECONDS,
)
from ingestion.config import GOOGLE_NEWS_RSS_TEMPLATE, TOPIC_CATEGORIES, USER_AGENTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _polite_delay() -> None:
    time.sleep(random.uniform(REQUEST_DELAY_MIN_SECONDS, REQUEST_DELAY_MAX_SECONDS))


def _normalize_published(entry) -> str | None:
    """Konversi published_parsed (struct_time UTC dari feedparser) ke ISO 8601."""
    parsed = getattr(entry, "published_parsed", None)
    if parsed:
        ts = calendar.timegm(parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return getattr(entry, "published", None)


def _is_within_age_range(entry, max_age_days: int) -> bool:

    parsed = getattr(entry, "published_parsed", None)
    if not parsed:
        return True
    published_dt = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return published_dt >= cutoff


def _decode_url(raw_url: str) -> str:
    try:
        decoded = gnewsdecoder(raw_url, interval=1)
        if decoded and decoded.get("status"):
            return decoded["decoded_url"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gagal decode URL %s: %s", raw_url, exc)
    return raw_url


def _extract_source_name(entry) -> str:
    source_obj = getattr(entry, "source", None)
    if isinstance(source_obj, dict):
        return source_obj.get("title", "Unknown Source")
    if hasattr(source_obj, "get"):
        return source_obj.get("title", "Unknown Source")
    return "Unknown Source"


def fetch_news(
    topic_categories: dict[str, list[str]] = TOPIC_CATEGORIES,
    max_per_query: int = MAX_ARTICLES_PER_TOPIC,
    max_age_days: int = MAX_ARTICLE_AGE_DAYS,
) -> list[dict]:
    """Scrape semua query di semua kategori topik, return list of article dict."""
    articles_data: list[dict] = []
    seen_urls: set[str] = set()

    for category, queries in topic_categories.items():
        for query in queries:
            encoded_query = quote(query)
            rss_url = GOOGLE_NEWS_RSS_TEMPLATE.format(query=encoded_query)

            feed = feedparser.parse(rss_url, request_headers={"User-Agent": _random_ua()})
            logger.info("[%s] query='%s' -> %d entries", category, query, len(feed.entries))

            # Sort by published_parsed (struct_time, reliable) terbaru dulu, sebelum
            # download+extract dijalankan, supaya limit max_per_query ambil artikel
            # paling baru -- bukan sekadar urutan asli dari RSS. Entry tanpa
            # published_parsed ditaruh paling akhir (dianggap tidak diketahui/terlama).
            sorted_entries = sorted(
                feed.entries,
                key=lambda e: getattr(e, "published_parsed", None) or time.gmtime(0),
                reverse=True,
            )

            # Filter by date range (bukan limit by count): hanya proses entry
            # yang terbit dalam `max_age_days` hari terakhir. Entry tanpa tanggal
            # (published_parsed None) tetap lolos -- lihat _is_within_age_range.
            # max_per_query tetap dipakai sebagai safety cap di bawah, supaya kalau
            # ada ratusan entry valid dalam rentang tanggal ini tidak semuanya
            # di-scrape sekaligus; tapi kalau cuma sedikit entry yang lolos filter
            # tanggal, tidak dipaksa mundur ke entry yang lebih lama demi capai cap.
            filtered_entries = [e for e in sorted_entries if _is_within_age_range(e, max_age_days)]
            skipped_old = len(sorted_entries) - len(filtered_entries)
            logger.info(
                "[%s] query='%s' -> %d/%d entries dalam %d hari terakhir (%d di-skip karena terlalu lama)",
                category,
                query,
                len(filtered_entries),
                len(sorted_entries),
                max_age_days,
                skipped_old,
            )

            count = 0
            for entry in filtered_entries:
                if count >= max_per_query:
                    break

                raw_url = entry.link
                url = _decode_url(raw_url)
                if url in seen_urls:
                    continue

                title_raw = entry.title
                published = _normalize_published(entry)
                source_name = _extract_source_name(entry)

                try:
                    article = Article(url, browser_user_agent=_random_ua())
                    article.download()
                    article.parse()
                    content = article.text.strip()

                    if len(content) < MIN_CONTENT_LENGTH:
                        logger.info("SKIP (konten < %d char): %s", MIN_CONTENT_LENGTH, url)
                        continue

                    articles_data.append(
                        {
                            "title": article.title or title_raw,
                            "url": url,
                            "published": published,
                            "content": content,
                            "source": source_name,
                            "topic_category": category,
                            "search_query": query,
                        }
                    )
                    seen_urls.add(url)
                    count += 1
                    logger.info("OK: %s", url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ERROR extracting %s: %s", url, exc)

                _polite_delay()

    return articles_data


def save_articles(articles: list[dict], filename: str) -> Path:
    """Simpan artikel ke JSON, APPEND ke histori yang sudah ada (dedup by URL).

    Kalau file `filename` sudah ada, artikel lama dibaca dulu lalu digabung
    dengan artikel baru. Artikel baru yang URL-nya sudah ada di histori di-skip,
    supaya file tidak numpuk duplikat persis dari run ke run.
    """
    out_path = RAW_DATA_DIR / filename

    existing_articles: list[dict] = []
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            existing_articles = json.load(f)

    seen_urls = {a.get("url") for a in existing_articles}
    new_count = 0
    for article in articles:
        if article.get("url") in seen_urls:
            continue
        existing_articles.append(article)
        seen_urls.add(article.get("url"))
        new_count += 1

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(existing_articles, f, ensure_ascii=False, indent=2)
    logger.info(
        "Saved %d new articles (%d skipped duplikat) -> %s (total histori: %d)",
        new_count,
        len(articles) - new_count,
        out_path,
        len(existing_articles),
    )
    return out_path


if __name__ == "__main__":
    news = fetch_news()
    save_articles(news, f"news_raw_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json")
