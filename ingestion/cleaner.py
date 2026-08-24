"""
Cleaning step antara scrape dan vectorize (dipakai sebagai task terpisah di Airflow DAG).

- Drop artikel dengan field wajib kosong (title/url/content).
- Re-validate panjang konten minimum (jaga-jaga kalau scraper berubah).
- Dedupe berdasarkan URL (dan title yang identik).
- Normalize whitespace berlebih di content.
"""
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.settings import MIN_CONTENT_LENGTH, PROCESSED_DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("title", "url", "content")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _normalize_whitespace(text: str) -> str:
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def clean_articles(articles: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for article in articles:
        if not all(article.get(f) for f in REQUIRED_FIELDS):
            continue

        url = article["url"].strip()
        title = article["title"].strip()
        content = _normalize_whitespace(article["content"])

        if len(content) < MIN_CONTENT_LENGTH:
            continue
        if url in seen_urls or title in seen_titles:
            continue

        article = {**article, "title": title, "url": url, "content": content}
        cleaned.append(article)
        seen_urls.add(url)
        seen_titles.add(title)

    logger.info("Cleaned %d -> %d artikel", len(articles), len(cleaned))
    return cleaned


def clean_file(raw_path: Path, out_filename: str) -> Path:
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_articles = json.load(f)

    cleaned = clean_articles(raw_articles)

    out_path = PROCESSED_DATA_DIR / out_filename
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    logger.info("Saved cleaned articles -> %s", out_path)
    return out_path


if __name__ == "__main__":
    import glob

    raw_files = sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "data" / "raw" / "*.json")))
    if not raw_files:
        raise SystemExit("Tidak ada file raw di data/raw/, jalankan scraper.py dulu.")
    latest = Path(raw_files[-1])
    clean_file(latest, latest.name.replace("news_raw_", "news_clean_"))
