"""
TrendPulse API - /api/trends
Fetches real data from Reddit (PRAW) and X/Twitter trends (scraping trends24.in)
Returns momentum scores 0-100 for each ticker
"""

import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from http.server import BaseHTTPRequestHandler

import praw
import requests
from bs4 import BeautifulSoup

from _signals import extract_tickers, calc_sentiment, calc_momentum


# ============================================================================
# Config
# ============================================================================

REDDIT_SUBREDDITS = ['wallstreetbets', 'cryptocurrency']
POSTS_PER_SUB = 50  # hot + rising combined


# ============================================================================
# Reddit Scraper (PRAW)
# ============================================================================

def get_reddit_client():
    """Initialize PRAW Reddit client."""
    return praw.Reddit(
        client_id=os.environ.get('REDDIT_CLIENT_ID'),
        client_secret=os.environ.get('REDDIT_CLIENT_SECRET'),
        username=os.environ.get('REDDIT_USERNAME'),
        password=os.environ.get('REDDIT_PASSWORD'),
        user_agent='TrendPulse/1.0'
    )


def fetch_reddit_data() -> dict:
    """Fetch posts from Reddit and aggregate by ticker."""
    try:
        reddit = get_reddit_client()
        ticker_data = defaultdict(lambda: {'mentions': 0, 'sentiment_sum': 0, 'scores': [], 'posts': 0, 'subreddit': ''})
        
        for sub_name in REDDIT_SUBREDDITS:
            subreddit = reddit.subreddit(sub_name)
            
            # Fetch hot + rising posts
            posts = list(subreddit.hot(limit=POSTS_PER_SUB // 2)) + list(subreddit.rising(limit=POSTS_PER_SUB // 2))
            
            for post in posts:
                text = f"{post.title} {post.selftext or ''}"
                tickers = extract_tickers(text)
                sentiment = calc_sentiment(text)
                
                for ticker in tickers:
                    ticker_data[ticker]['mentions'] += 1
                    ticker_data[ticker]['sentiment_sum'] += sentiment
                    ticker_data[ticker]['scores'].append(post.score)
                    ticker_data[ticker]['posts'] += 1
                    ticker_data[ticker]['subreddit'] = sub_name
        
        return dict(ticker_data)
    
    except Exception as e:
        print(f"Reddit error: {e}")
        return {}


# ============================================================================
# X/Twitter Trends Scraper (via trends24.in - no auth needed)
# ============================================================================

def fetch_twitter_trends() -> list:
    """Scrape trending topics from trends24.in (mirrors Twitter trends)."""
    try:
        # US trends
        url = "https://trends24.in/united-states/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        trends = []
        
        # Find trend list items
        trend_cards = soup.select('.trend-card__list li a')
        
        for item in trend_cards[:30]:  # Top 30 trends
            text = item.get_text(strip=True)
            if text:
                # Check if it contains a ticker
                tickers = extract_tickers(text.upper())
                if tickers:
                    for ticker in tickers:
                        trends.append({
                            'ticker': ticker,
                            'trend_text': text,
                            'source': 'twitter'
                        })
                # Also check for crypto/stock keywords
                elif any(kw in text.lower() for kw in ['stock', 'crypto', 'bitcoin', 'ethereum', '$']):
                    trends.append({
                        'ticker': text[:10],
                        'trend_text': text,
                        'source': 'twitter'
                    })
        
        return trends
    
    except Exception as e:
        print(f"Twitter trends error: {e}")
        return []


# ============================================================================
# Main Handler
# ============================================================================

def build_response():
    """Build the trends response combining Reddit and Twitter data."""
    trends = []
    
    # Reddit data
    reddit_data = fetch_reddit_data()
    for ticker, data in reddit_data.items():
        avg_sentiment = data['sentiment_sum'] / max(1, data['mentions'])
        avg_score = sum(data['scores']) / max(1, len(data['scores']))
        momentum = calc_momentum(data['mentions'], avg_score, avg_sentiment)
        
        trends.append({
            'ticker': f"${ticker}",
            'source': 'reddit',
            'momentum': momentum,
            'mentions': data['mentions'],
            'sentiment': round(avg_sentiment, 2),
            'subreddit': data['subreddit'],
            'posts': data['posts']
        })
    
    # Twitter trends
    twitter_data = fetch_twitter_trends()
    twitter_tickers = defaultdict(int)
    for t in twitter_data:
        twitter_tickers[t['ticker']] += 1
    
    for ticker, count in twitter_tickers.items():
        # Twitter trends get moderate momentum (we don't have sentiment)
        momentum = min(80, 30 + count * 10)
        
        # Check if also on Reddit (boost)
        if ticker.replace('$', '') in reddit_data:
            momentum = min(95, momentum + 15)
        
        trends.append({
            'ticker': f"${ticker}" if not ticker.startswith('$') else ticker,
            'source': 'twitter',
            'momentum': momentum,
            'mentions': count,
            'sentiment': 0.1,  # Neutral-positive assumption for trending
            'subreddit': None,
            'posts': 0
        })
    
    # Sort by momentum
    trends.sort(key=lambda x: x['momentum'], reverse=True)
    
    # Dedupe by ticker (keep highest momentum)
    seen = set()
    unique_trends = []
    for t in trends:
        ticker = t['ticker'].upper()
        if ticker not in seen:
            seen.add(ticker)
            unique_trends.append(t)
    
    return {
        'trends': unique_trends[:20],  # Top 20
        'updated': datetime.utcnow().isoformat(),
        'sources': {
            'reddit': len(reddit_data),
            'twitter': len(twitter_tickers)
        }
    }


# Vercel serverless handler
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
