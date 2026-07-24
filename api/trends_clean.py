"""
TrendPulse API - /api/trends
Stocktwits + Twitter/X Trends (via trends24.in)
"""

import re
import json
from datetime import datetime, timezone
from collections import defaultdict
from http.server import BaseHTTPRequestHandler

import requests
from bs4 import BeautifulSoup


# Config
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')

KNOWN_TICKERS = {
    'NVDA', 'TSLA', 'AMD', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
    'GME', 'AMC', 'PLTR', 'SOFI', 'HOOD', 'COIN', 'MSTR', 'SPY', 'QQQ',
    'SMCI', 'ARM', 'AVGO', 'MU', 'INTC', 'BA', 'DIS', 'NFLX', 'PYPL',
    'BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'DOT', 'AVAX', 'MATIC',
    'LINK', 'SHIB', 'PEPE', 'BONK', 'WIF', 'ARB', 'OP', 'SUI', 'APT',
}

KEYWORD_TO_TICKER = {
    'bitcoin': 'BTC', 'btc': 'BTC', 'ethereum': 'ETH', 'eth': 'ETH',
    'solana': 'SOL', 'dogecoin': 'DOGE', 'doge': 'DOGE', 'nvidia': 'NVDA',
    'tesla': 'TSLA', 'apple': 'AAPL', 'microsoft': 'MSFT', 'amazon': 'AMZN',
    'google': 'GOOGL', 'gamestop': 'GME', 'palantir': 'PLTR'
}

FINANCE_KEYWORDS = {'crypto', 'stock', 'trading', 'market', 'nasdaq', 'nyse', 'earnings', 'ipo'}
BULLISH = {'moon', 'pump', 'bullish', 'buy', 'rally', 'surge', 'breakout', 'ath', 'calls', 'green'}
BEARISH = {'dump', 'crash', 'bearish', 'sell', 'plunge', 'tank', 'drop', 'puts', 'red', 'fear'}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}


def fetch_stocktwits():
    """Fetch trending tickers from Stocktwits API (free, no auth)."""
    try:
        resp = requests.get(
            "https://api.stocktwits.com/api/2/trending/symbols.json",
            headers=HEADERS, timeout=15
        )
        if resp.status_code != 200:
            return []
        
        symbols = resp.json().get('symbols', [])
        return [{
            'ticker': s.get('symbol', ''),
            'name': s.get('title', ''),
            'rank': i + 1,
            'watchlist': s.get('watchlist_count', 0)
        } for i, s in enumerate(symbols[:30]) if s.get('symbol')]
    except Exception as e:
        print(f"Stocktwits error: {e}")
        return []


def fetch_twitter():
    """Scrape finance-related trends from trends24.in."""
    try:
        resp = requests.get(
            "https://trends24.in/united-states/",
            headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        trends = []
        for i, item in enumerate(soup.select('.trend-card__list li a')[:50]):
            text = item.get_text(strip=True)
            if not text:
                continue
            
            tickers = []
            text_lower = text.lower()
            
            # Extract $TICKER mentions
            for match in TICKER_PATTERN.findall(text.upper()):
                if match in KNOWN_TICKERS:
                    tickers.append(match)
            
            # Map keywords to tickers
            for kw, ticker in KEYWORD_TO_TICKER.items():
                if kw in text_lower and ticker not in tickers:
                    tickers.append(ticker)
            
            # Check for finance keywords
            is_finance = bool(tickers) or any(kw in text_lower for kw in FINANCE_KEYWORDS)
            
            if is_finance or tickers:
                trends.append({'text': text, 'rank': i + 1, 'tickers': tickers})
        
        return trends
    except Exception as e:
        print(f"Twitter trends error: {e}")
        return []


def calc_sentiment(text=''):
    """Simple sentiment from keyword matching."""
    if not text:
        return 0.1
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH if w in text_lower)
    bear = sum(1 for w in BEARISH if w in text_lower)
    if bull + bear == 0:
        return 0.1
    return round((bull - bear) / (bull + bear), 2)


def calc_momentum(rank, mentions=1, sentiment=0.1, watchlist=0):
    """Calculate momentum score 0-100."""
    rank_score = max(0, 50 - rank) * 0.8  # 0-40 pts
    mention_score = min(30, mentions * 5 + (watchlist / 1000))  # 0-30 pts
    sentiment_score = (sentiment + 1) * 15  # 0-30 pts
    return int(min(100, max(0, rank_score + mention_score + sentiment_score)))


def build_response():
    """Aggregate trends from all sources."""
    ticker_data = defaultdict(lambda: {
        'mentions': 0, 'best_rank': 999, 'sentiment_sum': 0,
        'sources': set(), 'context': [], 'watchlist': 0
    })
    
    # Stocktwits data
    stocktwits = fetch_stocktwits()
    for item in stocktwits:
        t = item['ticker']
        ticker_data[t]['mentions'] += 1
        ticker_data[t]['best_rank'] = min(ticker_data[t]['best_rank'], item['rank'])
        ticker_data[t]['sentiment_sum'] += 0.15
        ticker_data[t]['sources'].add('stocktwits')
        ticker_data[t]['context'].append(item.get('name', t))
        ticker_data[t]['watchlist'] = item.get('watchlist', 0)
    
    # Twitter data
    twitter = fetch_twitter()
    for item in twitter:
        sentiment = calc_sentiment(item['text'])
        for t in item['tickers']:
            ticker_data[t]['mentions'] += 1
            ticker_data[t]['best_rank'] = min(ticker_data[t]['best_rank'], item['rank'])
            ticker_data[t]['sentiment_sum'] += sentiment
            ticker_data[t]['sources'].add('twitter')
            ticker_data[t]['context'].append(item['text'][:40])
    
    # Build final list
    trends = []
    for ticker, data in ticker_data.items():
        avg_sent = data['sentiment_sum'] / max(1, data['mentions'])
        momentum = calc_momentum(data['best_rank'], data['mentions'], avg_sent, data['watchlist'])
        
        # Boost multi-source tickers
        if len(data['sources']) > 1:
            momentum = min(100, momentum + 10)
        
        trends.append({
            'ticker': f'${ticker}',
            'source': 'multi' if len(data['sources']) > 1 else list(data['sources'])[0],
            'momentum': momentum,
            'mentions': data['mentions'],
            'sentiment': round(avg_sent, 2),
            'rank': data['best_rank'],
            'context': list(set(data['context']))[:3]
        })
    
    trends.sort(key=lambda x: x['momentum'], reverse=True)
    
    return {
        'trends': trends[:20],
        'updated': datetime.now(timezone.utc).isoformat(),
        'sources': {'stocktwits': len(stocktwits), 'twitter': len(twitter)},
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = build_response()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'max-age=60')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()


if __name__ == '__main__':
    import sys
    print("Testing TrendPulse API...", file=sys.stderr)
    result = build_response()
    print(json.dumps(result, indent=2))
