"""
TrendPulse scraper — drives a real, logged-in browser under your own
Reddit and X accounts to find ticker mentions, instead of the Reddit API
(PRAW) or a trends24.in mirror. Personal use only.

Run directly (not via the API): `python scraper/run_scraper.py`

First run:
  A visible Chromium window opens to Reddit and X. Log in manually in
  that window (once), then press Enter in this terminal. The session is
  saved to scraper/browser_profile/ (gitignored — it holds real login
  cookies) so later runs skip the login step.

Every cycle it writes the combined snapshot to data/latest_trends.json,
which api/trends.py just reads and serves — decoupled so a slow browser
scan is never on the hook for a request/response deadline.
"""

import os
import sys
import json
import time
from collections import defaultdict
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api'))
from _signals import extract_tickers, calc_sentiment, calc_momentum  # noqa: E402
from _logging_setup import get_logger  # noqa: E402

log = get_logger('scraper')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PROFILE_DIR = os.path.join(SCRIPT_DIR, 'browser_profile')
DATA_FILE = os.path.join(PROJECT_ROOT, 'data', 'latest_trends.json')

REDDIT_SUBREDDITS = ['wallstreetbets', 'cryptocurrency']
POSTS_PER_LISTING = 25  # per subreddit per sort (hot/rising)
SCRAPE_INTERVAL_SECONDS = int(os.environ.get('SCRAPE_INTERVAL_SECONDS', '300'))


# ============================================================================
# Reddit — old.reddit.com listing pages (stable, server-rendered DOM;
# the new React UI churns its markup far more often)
# ============================================================================

def scrape_reddit(context) -> dict:
    """Scrape post titles + scores from wallstreetbets/cryptocurrency while logged in.

    Note: only the post title is scraped (not selftext) — listing pages
    don't expose selftext without opening each post individually, which
    would be far slower per cycle. Titles carry the ticker/sentiment
    signal in the large majority of WSB/crypto posts.
    """
    ticker_data = defaultdict(lambda: {'mentions': 0, 'sentiment_sum': 0, 'scores': [], 'posts': 0, 'subreddit': ''})
    page = context.new_page()
    try:
        for sub in REDDIT_SUBREDDITS:
            for sort in ('hot', 'rising'):
                url = f'https://old.reddit.com/r/{sub}/{sort}/'
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                except Exception as e:
                    log.error(f"Reddit fetch failed for {url}: {e}")
                    continue

                posts = page.query_selector_all('div.thing')
                for post in posts[:POSTS_PER_LISTING]:
                    title_el = post.query_selector('a.title')
                    if not title_el:
                        continue
                    title = title_el.inner_text()

                    score = 1
                    score_el = post.query_selector('div.score.unvoted')
                    if score_el:
                        raw = score_el.get_attribute('title')
                        if raw and raw.lstrip('-').isdigit():
                            score = int(raw)

                    tickers = extract_tickers(title)
                    sentiment = calc_sentiment(title)

                    for ticker in tickers:
                        d = ticker_data[ticker]
                        d['mentions'] += 1
                        d['sentiment_sum'] += sentiment
                        d['scores'].append(score)
                        d['posts'] += 1
                        d['subreddit'] = sub
    finally:
        page.close()

    return dict(ticker_data)


# ============================================================================
# X/Twitter — live Explore/Trending page while logged in
# (replaces both the trends24.in mirror and the old local Selenium script)
# ============================================================================

def scrape_x_trends(context) -> list:
    trends = []
    page = context.new_page()
    try:
        page.goto('https://x.com/explore/tabs/trending', wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(2000)  # let the trend list hydrate

        cells = page.query_selector_all('div[data-testid="trend"]')
        for cell in cells[:30]:
            text = cell.inner_text().replace('\n', ' ').strip()
            if not text:
                continue

            tickers = extract_tickers(text.upper())
            if tickers:
                for ticker in tickers:
                    trends.append({'ticker': ticker, 'trend_text': text, 'source': 'twitter'})
            elif any(kw in text.lower() for kw in ['stock', 'crypto', 'bitcoin', 'ethereum', '$']):
                trends.append({'ticker': text[:10], 'trend_text': text, 'source': 'twitter'})
    except Exception as e:
        log.error(f"X trending fetch failed: {e}")
    finally:
        page.close()

    return trends


# ============================================================================
# Combine into the same response shape App.jsx already expects
# ============================================================================

def build_snapshot(reddit_data: dict, twitter_data: list) -> dict:
    trends = []

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
            'posts': data['posts'],
        })

    twitter_tickers = defaultdict(int)
    for t in twitter_data:
        twitter_tickers[t['ticker']] += 1

    for ticker, count in twitter_tickers.items():
        momentum = min(80, 30 + count * 10)
        if ticker.replace('$', '') in reddit_data:
            momentum = min(95, momentum + 15)

        trends.append({
            'ticker': f"${ticker}" if not ticker.startswith('$') else ticker,
            'source': 'twitter',
            'momentum': momentum,
            'mentions': count,
            'sentiment': 0.1,
            'subreddit': None,
            'posts': 0,
        })

    trends.sort(key=lambda x: x['momentum'], reverse=True)

    seen = set()
    unique_trends = []
    for t in trends:
        ticker = t['ticker'].upper()
        if ticker not in seen:
            seen.add(ticker)
            unique_trends.append(t)

    return {
        'trends': unique_trends[:20],
        'updated': datetime.now(timezone.utc).isoformat(),
        'sources': {'reddit': len(reddit_data), 'twitter': len(twitter_tickers)},
    }


def write_snapshot(snapshot: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    tmp_path = DATA_FILE + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f)
    os.replace(tmp_path, DATA_FILE)  # atomic — api/trends.py never reads a half-written file


# ============================================================================
# Login + main loop
# ============================================================================

def ensure_logged_in(context):
    reddit_page = context.new_page()
    # old.reddit.com rather than www.reddit.com — the new React site runs a much
    # more aggressive bot-detection challenge; old.reddit's login still
    # authenticates the same reddit.com session cookies, and it's where the
    # scraper reads from anyway.
    reddit_page.goto('https://old.reddit.com/', wait_until='domcontentloaded', timeout=30000)
    x_page = context.new_page()
    x_page.goto('https://x.com/', wait_until='domcontentloaded', timeout=30000)

    print('\nIf either tab shows a login page, log in now in the opened browser window.')
    input("Press Enter here once you're logged into both Reddit and X to start scraping... ")
    log.info('Login gate cleared, starting scan loop')

    reddit_page.close()
    x_page.close()


def launch_context(p):
    """Launch the persistent browser, preferring real installed Chrome over
    Playwright's bundled Chromium build — Reddit/X's bot-detection specifically
    fingerprints the bundled build far more aggressively than a real Chrome
    install. Also strips the automation flags that make navigator.webdriver
    true and trigger the "Chrome is being controlled by automated test
    software" banner in the first place.
    """
    common_kwargs = dict(
        headless=False,
        viewport={'width': 1280, 'height': 900},
        args=['--disable-blink-features=AutomationControlled'],
        ignore_default_args=['--enable-automation'],
    )
    try:
        return p.chromium.launch_persistent_context(PROFILE_DIR, channel='chrome', **common_kwargs)
    except Exception as e:
        log.warning(f"Real Chrome not available ({e}); falling back to bundled Chromium "
                    f"(more likely to get bot-detection challenges). Run "
                    f"`playwright install chrome` to fix this.")
        return p.chromium.launch_persistent_context(PROFILE_DIR, **common_kwargs)


def main():
    with sync_playwright() as p:
        context = launch_context(p)
        ensure_logged_in(context)

        log.info(f"Scanning every {SCRAPE_INTERVAL_SECONDS}s. Ctrl+C to stop.")
        while True:
            cycle_start = time.time()
            try:
                log.info('Scan starting...')
                reddit_data = scrape_reddit(context)
                twitter_data = scrape_x_trends(context)
                snapshot = build_snapshot(reddit_data, twitter_data)
                write_snapshot(snapshot)
                log.info(f"Scan complete — {len(snapshot['trends'])} tickers written to {DATA_FILE}")
            except Exception:
                log.exception('Scan failed')

            elapsed = time.time() - cycle_start
            time.sleep(max(5, SCRAPE_INTERVAL_SECONDS - elapsed))


if __name__ == '__main__':
    main()
