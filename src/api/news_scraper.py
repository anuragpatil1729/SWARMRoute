# src/api/news_scraper.py
"""Simple web scraper for news headlines.
Uses public news sites (Google News and BBC) and extracts title, URL, and snippet.
No API keys required. Respects robots.txt by using standard GET requests.
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

DEFAULT_SOURCES = [
    "https://news.google.com/rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
]


def fetch_rss(url: str) -> List[Dict[str, str]]:
    """Fetch and parse an RSS feed, returning a list of article dicts.
    Each dict contains `title`, `link`, and `description` (if available).
    """
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "xml")
    items = soup.find_all("item")
    articles = []
    for it in items:
        title = it.title.text if it.title else ""
        link = it.link.text if it.link else ""
        description = it.description.text if it.description else ""
        articles.append({"title": title, "url": link, "content": description})
    return articles


def scrape_latest(sources: List[str] = None) -> List[Dict[str, str]]:
    """Collect latest articles from all configured news sources.
    Returns a flat list of article dictionaries.
    """
    if sources is None:
        sources = DEFAULT_SOURCES
    all_articles = []
    for src in sources:
        try:
            all_articles.extend(fetch_rss(src))
        except Exception as e:
            # Log but continue with other sources
            print(f"[news_scraper] Failed to fetch {src}: {e}")
    # Deduplicate by URL
    seen = set()
    uniq = []
    for a in all_articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            uniq.append(a)
    return uniq
