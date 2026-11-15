"""Detect "should I sell/buy <stock>?" in a chat message and resolve the stock.

Pure text matching, no model call. A stock is recognised by its ticker or by its company
name from the asset universe ("nvidia" -> NVDA, "shopify" -> SHOP.TO).
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from functools import lru_cache
from typing import Dict, Optional, Tuple

from app.services import reference_data


SELL_WORDS = r"sell|selling|vendre|vends|vendez|vendons"
BUY_WORDS = r"buy|buying|purchase|acheter|achete|achetez|achetons"
_ACTION = re.compile(rf"\b({SELL_WORDS}|{BUY_WORDS})\b")


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


# Everyday names that are not in the company name (and "SPDR" is shared by two funds).
SYNONYMS = {
    "gold": "GLD",
    "nasdaq": "QQQ",
    "s&p": "SPY",
    "s&p 500": "SPY",
    "sp500": "SPY",
    "tsx": "XIU.TO",
}


@lru_cache(maxsize=1)
def _aliases() -> Dict[str, str]:
    """Lowercase name or ticker alias -> ticker. Ambiguous aliases are dropped."""
    found: Dict[str, set] = {}

    def add(alias: str, ticker: str) -> None:
        alias = _fold(alias).strip()
        if len(alias) >= 2:
            found.setdefault(alias, set()).add(ticker)

    for row in csv.DictReader(io.StringIO(reference_data.read_text("assets_universe.csv"))):
        ticker, name = row["ticker"], row["name"]
        add(ticker, ticker)
        add(ticker.split(".")[0], ticker)
        add(name, ticker)
        first = re.split(r"[\s(]", name)[0]
        if len(first) >= 4:
            add(first, ticker)
    aliases = {alias: next(iter(t)) for alias, t in found.items() if len(t) == 1}
    aliases.update(SYNONYMS)
    return aliases


def parse(message: str) -> Optional[Tuple[str, str, Optional[str]]]:
    """Return ``(action, ticker, None)``, ``(action, "", mention)`` for an unknown stock, or None.

    None means this is not a trade question: it needs both a buy/sell word and a stock.
    """
    text = _fold(message)
    action_match = _ACTION.search(text)
    if not action_match:
        return None
    action = "sell" if re.fullmatch(SELL_WORDS, action_match.group(1)) else "buy"
    aliases = _aliases()
    # Longest alias first so "royal bank of canada" beats "royal".
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
            return action, aliases[alias], None
    return None


def resolve(text: str) -> Optional[str]:
    """Ticker for a ticker symbol or company name ("nvidia" -> NVDA), or None."""
    return _aliases().get(_fold(text).strip())
