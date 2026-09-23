# src/api/news_endpoint.py
"""FastAPI router exposing the news endpoint.
It scrapes the latest articles, runs them through the RoBERTa
zero‑shot classification + summarization pipeline, and returns JSON.
"""
from fastapi import APIRouter
from src.api.news_scraper import scrape_latest
from src.api.news_model import process_articles

router = APIRouter(prefix="/news", tags=["News"])

@router.get("/")
def get_news():
    """Return processed news articles.
    The response format is:
    {
        "articles": [
            {"title": ..., "url": ..., "content": ..., "summary": ..., "relevance": {...}},
            ...
        ]
    }
    """
    raw = scrape_latest()
    processed = process_articles(raw)
    return {"articles": processed}
