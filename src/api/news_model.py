# src/api/news_model.py
"""Load a RoBERTa model and provide simple NLP processing for news articles.
We use HuggingFace `transformers` with the `roberta-base` checkpoint.
Two pipelines are employed:
- Zero‑shot classification (relevance to "delivery route" topics)
- Summarization (short 2‑sentence summary)
Both run on CPU by default; if a GPU is available it will be used automatically.
"""
from typing import List, Dict

from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer, AutoModelForSeq2SeqLM

# Load the models lazily – they are instantiated on first use.
_classification_pipe = None
_summarization_pipe = None


def _get_classification_pipe():
    global _classification_pipe
    if _classification_pipe is None:
        model_name = "roberta-large-mnli"
        _classification_pipe = pipeline("zero-shot-classification", model=model_name, device=-1)
    return _classification_pipe


def _get_summarization_pipe():
    global _summarization_pipe
    if _summarization_pipe is None:
        model_name = "facebook/bart-large-cnn"
        _summarization_pipe = pipeline("summarization", model=model_name, device=-1)
    return _summarization_pipe


def _classify_article(text: str) -> Dict[str, float]:
    """Return a relevance score for the article with respect to delivery routes.
    We ask the zero‑shot model to evaluate the likelihood of the following labels:
    - "delivery"
    - "logistics"
    - "traffic"
    - "other"
    The function returns a dict mapping each label to its confidence.
    """
    pipe = _get_classification_pipe()
    hypothesis_template = "This text is about {}."
    result = pipe(
        text,
        candidate_labels=["delivery", "logistics", "traffic", "other"],
        hypothesis_template=hypothesis_template,
    )
    return dict(zip(result["labels"], result["scores"]))


def _summarize_article(text: str) -> str:
    """Generate a short summary (max 2 sentences) for the article body.
    If the article is too short, the original text is returned.
    """
    if not text or len(text.split()) < 30:
        return text.strip()
    pipe = _get_summarization_pipe()
    summary = pipe(text, max_length=60, min_length=20, do_sample=False)
    return summary[0]["summary_text"].strip()


def process_articles(articles: List[Dict[str, str]]) -> List[Dict[str, any]]:
    """Process a list of article dicts (as produced by `news_scraper`).
    For each article we compute:
    - `relevance` – a dict of label → confidence
    - `summary` – a short generated summary
    The returned list preserves the original order and includes the original fields.
    """
    processed = []
    for a in articles:
        content = a.get("content", "")
        relevance = _classify_article(content)
        summary = _summarize_article(content)
        processed.append({
            "title": a.get("title"),
            "url": a.get("url"),
            "content": content,
            "summary": summary,
            "relevance": relevance,
        })
    return processed
