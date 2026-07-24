"""
Shared ticker-extraction, sentiment, and momentum scoring logic.

Pure functions with no dependency on where the raw text came from
(Reddit API, browser-scraped Reddit/X, whatever comes next) — both the
Vercel-era api/trends.py and the local Playwright scraper reuse these
instead of re-deriving the same regexes/heuristics twice.
"""

import re
import math

# Ticker regex
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
TICKER_MENTION = re.compile(r'\b([A-Z]{2,5})\b')

# Known tickers (validates uppercase words)
KNOWN_TICKERS = {
    # Stocks
    'NVDA', 'TSLA', 'AMD', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
    'GME', 'AMC', 'PLTR', 'SOFI', 'HOOD', 'COIN', 'MSTR', 'SPY', 'QQQ',
    'SMCI', 'ARM', 'AVGO', 'MU', 'INTC', 'BA', 'DIS', 'NFLX', 'PYPL',
    # Crypto
    'BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'DOT', 'AVAX', 'MATIC',
    'LINK', 'SHIB', 'PEPE', 'BONK', 'WIF', 'ARB', 'OP', 'SUI', 'APT',
}

# Sentiment keywords
BULLISH = {'moon', 'pump', 'bullish', 'buy', 'calls', 'long', 'squeeze', 'rocket', 'tendies', 'diamond', '🚀', '📈', '💎'}
BEARISH = {'dump', 'crash', 'bearish', 'sell', 'puts', 'short', 'rekt', 'rug', '📉', '💀', '🐻'}


def extract_tickers(text: str) -> list:
    """Extract valid tickers from text."""
    tickers = set()

    # $TICKER format
    for match in TICKER_PATTERN.findall(text):
        if match in KNOWN_TICKERS:
            tickers.add(match)

    # Uppercase words (validate against known)
    for match in TICKER_MENTION.findall(text):
        if match in KNOWN_TICKERS:
            tickers.add(match)

    return list(tickers)


def calc_sentiment(text: str) -> float:
    """Calculate sentiment score -1 to 1."""
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH if w in text_lower)
    bear = sum(1 for w in BEARISH if w in text_lower)
    total = bull + bear
    if total == 0:
        return 0.0
    return round((bull - bear) / total, 2)


def calc_momentum(mentions: int, avg_score: float, sentiment: float) -> int:
    """
    Calculate momentum score 0-100.

    Factors:
    - Mention volume (log scaled, 40%)
    - Avg post score (log scaled, 30%)
    - Sentiment strength (30%)
    """
    # Mention score (0-40)
    mention_score = min(40, math.log10(max(1, mentions)) * 20)

    # Score score (0-30)
    score_score = min(30, math.log10(max(1, avg_score)) * 10)

    # Sentiment score (0-30)
    sentiment_score = (abs(sentiment) + 0.5) * 20  # Boost for strong sentiment
    sentiment_score = min(30, sentiment_score)

    momentum = int(mention_score + score_score + sentiment_score)
    return max(0, min(100, momentum))
