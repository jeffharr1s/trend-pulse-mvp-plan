"""
TrendPulse API - /api/trends
Twitter/X Trends + Stocktwits Trending - No Reddit required
"""

import re
import json
from datetime import datetime, timezone
from collections import defaultdict
from http.server import BaseHTTPRequestHandler

import requests
from bs4 import BeautifulSoup


TICKER_PATTERN = re.compile(r'$([A-Z]{1,5})\b')

KNOWN_TICKERS = {
    'NVDA', 'TSLA', 'AMD', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
    'GME', 'AMC', 'PLTR', 'SOFI', 'HOOD', 'COIN', 'MSTR', 'SPY', 'QQQ',
    'SMCI', 'ARM', 'AVGO', 'MU', 'INTC', 'BA', 'DIS', 'NFLX', 'PYPL',
    'BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'DOT', 'AVAX', 'MATIC',
    'LINK', 'SHIB', 'PEPE', 'BONK', 'WIF', 'ARB', 'OP', 'SUI', 'APT',
}

CRYPTO_KEYWORDS = {'bitcoin', 'ethereum', 'crypto', 'btc', 'eth', 'solana', 'dogecoin', 'xrp', 'cardano'}
STOCK_KEYWORDS = {'stock', 'trading', 'market', 'nasdaq', 'nyse', 'earnings', 'ipo'}

BULLISH = {'moon', 'pump', 'bullish', 'buy', 'rally', 'surge', 'soar', 'breakout', 'ath', 'record', 'up', 'green', 'calls'}
BEARISH = {'dump', 'crash', 'bearish', 'sell', 'plunge', 'tank', 'drop', 'collapse', 'fear', 'down', 'red', 'puts'}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def fetch_stocktwits_trending():
    trends = []
    try:
        url = "https://api.stocktwits.com/api/2/trending/symbols.json"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            symbols = data.get('symbols', [])
            for idx, sym in enumerate(symbols[:30]):
                ticker = sym.get('symbol', '')
                title = sym.get('title', ticker)
                if ticker:
                    trends.append({
                        'ticker': ticker,
                        'name': title,
                        'rank': idx + 1,
                        'source': 'stocktwits',
                        'watchlist_count': sym.get('watchlist_count', 0)
                    })
            print(f"Stocktwits: Got {len(trends)} trending symbols")
            return trends
    except Exception as e:
        print(f"Stocktwits API error: {e}")
    return trends


def fetch_twitter_trends():
    trends = []
    try:
        url = "https://trends24.in/united-states/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        trend_cards = soup.select('.trend-card__list li a')
        for idx, item in enumerate(trend_cards[:50]):
            text = item.get_text(strip=True)
            if not text:
                continue
            trend_data = {'text': text, 'rank': idx + 1, 'tickers': [], 'is_finance': False}
            for match in TICKER_PATTERN.findall(text.upper()):
                if match in KNOWN_TICKERS:
                    trend_data['tickers'].append(match)
                    trend_data['is_finance'] = True
            text_lower = text.lower()
            if any(kw in text_lower for kw in CRYPTO_KEYWORDS | STOCK_KEYWORDS):
                trend_data['is_finance'] = True
                keyword_map = {'bitcoin': 'BTC', 'btc': 'BTC', 'ethereum': 'ETH', 'eth': 'ETH',
                    'solana': 'SOL', 'dogecoin': 'DOGE', 'doge': 'DOGE', 'nvidia': 'NVDA', 
                    'tesla': 'TSLA', 'apple': 'AAPL', 'microsoft': 'MSFT', 'amazon': 'AMZN', 'google': 'GOOGL'}
                for kw, ticker in keyword_map.items():
                    if kw in text_lower:
                        trend_data['tickers'].append(ticker)
            if trend_data['tickers'] or trend_data['is_finance']:
                trends.append(trend_data)
        print(f"Twitter: Got {len(trends)} finance-related trends")
    except Exception as e:
        print(f"Twitter trends error: {e}")
    return trends


def calc_sentiment(text=''):
    if not text:
        return 0.15
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH if w in text_lower)
    bear = sum(1 for w in BEARISH if w in text_lower)
    if bull + bear == 0:
        return 0.1
    return round((bull - bear) / (bull + bear), 2)


def calc_momentum(rank, mentions=1, sentiment=0.1, watchlist=0):
    rank_score = max(0, 50 - rank) * 0.8
    mention_score = min(30, mentions * 5 + (watchlist / 1000))
    sentiment_score = (sentiment + 1) * 15
    return int(min(100, max(0, rank_score + mention_score + sentiment_score)))


def build_response():
    ticker_data = defaultdict(lambda: {'mentions': 0, 'best_rank': 999, 'sentiment_sum': 0, 'sources': set(), 'context': [], 'watchlist': 0})
    
    stocktwits = fetch_stocktwits_trending()
    for item in stocktwits:
        ticker = item['ticker']
        ticker_data[ticker]['mentions'] += 1
        ticker_data[ticker]['best_rank'] = min(ticker_data[ticker]['best_rank'], item['rank'])
        ticker_data[ticker]['sentiment_sum'] += 0.15
        ticker_data[ticker]['sources'].add('stocktwits')
        ticker_data[ticker]['context'].append(item.get('name', ticker))
        ticker_data[ticker]['watchlist'] = item.get('watchlist_count', 0)
    
    twitter = fetch_twitter_trends()
    for item in twitter:
        sentiment = calc_sentiment(item['text'])
        for ticker in item['tickers']:
            ticker_data[ticker]['mentions'] += 1
            ticker_data[ticker]['best_rank'] = min(ticker_data[ticker]['best_rank'], item['rank'])
            ticker_data[ticker]['sentiment_sum'] += sentiment
            ticker_data[ticker]['sources'].add('twitter')
            ticker_data[ticker]['context'].append(item['text'][:40])
    
    trends = []
    for ticker, data in ticker_data.items():
        avg_sentiment = data['sentiment_sum'] / max(1, data['mentions'])
        momentum = calc_momentum(data['best_rank'], data['mentions'], avg_sentiment, data['watchlist'])
        if len(data['sources']) > 1:
            momentum = min(100, momentum + 10)
        trends.append({
            'ticker': f'${ticker}',
            'source': list(data['sources'])[0] if len(data['sources']) == 1 else 'multi',
            'momentum': momentum,
            'mentions': data['mentions'],
            'sentiment': round(avg_sentiment, 2),
            'rank': data['best_rank'],
            'context': list(set(data['context']))[:3]
        })
    
    trends.sort(key=lambda x: x['momentum'], reverse=True)
    
    return {
        'trends': trends[:20],
        'updated': datetime.now(timezone.utc).isoformat(),
        'sources': {'stocktwits': len(stocktwits), 'twitter': len(twitter), 'reddit': 0},
        'note': 'Stocktwits + X trends - Reddit pending API approval'
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


if __name__ == '__main__':
    print("=" * 50)
    print("TrendPulse API Test")
    print("=" * 50)
    result = build_response()
    print(json.dumps(result, indent=2))
