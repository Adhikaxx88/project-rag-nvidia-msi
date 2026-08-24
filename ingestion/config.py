"""
Daftar topik pencarian & User-Agent pool untuk scraper Google News RSS.
Topik dibagi 2 kategori sesuai spesifikasi:
  - fed_specific : keputusan suku bunga, FOMC, Powell, CPI/PCE, Treasury yields, dollar index
  - global_macro  : recession/growth outlook, ECB, China slowdown, oil/commodity, market
                     volatility, emerging markets currency crisis
"""

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

FED_SPECIFIC_QUERIES = [
    "Federal Reserve interest rate decision FOMC meeting",
    "Fed chair speech monetary policy statement",
    "US CPI PCE inflation data Fed rate policy",
    "US Treasury yields dollar index Fed rate outlook",
    "Fed rate hike rate cut hawkish dovish",
    "US unemployment jobs report labor market Fed",
    "US GDP growth economic data Fed policy",
    "Fed balance sheet quantitative tightening easing",
]

GLOBAL_MACRO_QUERIES = [
    "global economy recession growth outlook IMF World Bank",
    "European Central Bank ECB interest rate policy eurozone inflation",
    "China economy slowdown trade GDP global markets",
    "oil prices energy crisis commodity markets global inflation",
    "global stock market volatility geopolitical risk economy",
    "emerging markets currency crisis debt global economic outlook",
    "Bank of Japan Bank of England interest rate policy",
    "gold prices safe haven investment global markets",
    "global trade war tariffs economic impact",
    "cryptocurrency bitcoin market Fed interest rate impact",
    "US stock market S&P 500 earnings economic outlook",
    "global supply chain inflation economic disruption",
]

TOPIC_CATEGORIES = {
    "fed_specific": FED_SPECIFIC_QUERIES,
    "global_macro": GLOBAL_MACRO_QUERIES,
}

GOOGLE_NEWS_RSS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
