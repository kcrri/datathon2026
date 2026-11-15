"""Knowledge base tool: matches a question to an FAQ entry and the wiki agents that own it."""
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.i18n import normalize

_DIR = Path(__file__).parents[1] / "knowledge"
FAQS: Dict[str, List[Dict[str, Any]]] = {
    "en": json.loads((_DIR / "faq.json").read_text()),
    "fr": json.loads((_DIR / "faq.fr.json").read_text()),
}
FAQ = FAQS["en"]  # kept for callers that import the English list


def _fold(text: str) -> str:
    """Lowercase, drop accents and normalise apostrophes so 'récession' matches 'recession'."""
    text = text.lower().replace("\u2019", "'")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _hits(keyword: str, text: str) -> int:
    key = _fold(keyword)
    if len(key) <= 3:  # short keywords must be whole words ("or", "eth", "dca")
        return len(key) if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", text) else 0
    return len(key) if key in text else 0


def _best(entries: List[Dict[str, Any]], text: str) -> Optional[Dict[str, Any]]:
    best, score = None, 0
    for entry in entries:
        hits = sum(_hits(k, text) for k in entry["keywords"])
        if hits > score:
            best, score = entry, hits
    return best


def match(message: str, lang: str = "en") -> Optional[Dict[str, Any]]:
    """Best FAQ entry for the message, written in ``lang``. The other language is tried as a fallback."""
    lang = normalize(lang)
    text = _fold(message)
    other = "fr" if lang == "en" else "en"
    for source in (lang, other):
        found = _best(FAQS[source], text)
        if found:
            return next((e for e in FAQS[lang] if e["id"] == found["id"]), found)
    return None


def suggestions(lang: str = "en"):
    return [e["question"] for e in FAQS[normalize(lang)][:5]]
