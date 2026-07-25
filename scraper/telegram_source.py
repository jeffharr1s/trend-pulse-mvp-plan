"""
TrendPulse Telegram source.

Unlike Reddit/X, this needs no login and no browser automation: public
Telegram channels expose a lightweight HTML preview at t.me/s/<channel>,
readable with a plain HTTP GET. No bot-detection fight, no account to
put at risk.

There's no Telegram equivalent of "trending" — you have to name the
channels to watch. Set TELEGRAM_CHANNELS in .env as a comma-separated
list of channel usernames (no @, e.g. "wallstreetbets,cryptosignals").
Empty by default; scrape_telegram_channels() just returns [] until set.
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api'))
from _logging_setup import get_logger  # noqa: E402
from _signals import extract_tickers, calc_sentiment  # noqa: E402

log = get_logger('scraper')

MESSAGES_PER_CHANNEL = 20
REQUEST_TIMEOUT = 10
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def get_configured_channels() -> list:
    raw = os.environ.get('TELEGRAM_CHANNELS', '')
    return [c.strip().lstrip('@') for c in raw.split(',') if c.strip()]


def scrape_telegram_channels(channels: list = None) -> list:
    """Returns a list of {ticker, trend_text, source, sentiment, channel} dicts,
    one per ticker mention found in each channel's recent messages.
    """
    channels = get_configured_channels() if channels is None else channels
    if not channels:
        return []

    mentions = []
    for channel in channels:
        url = f'https://t.me/s/{channel}'
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.error(f'Telegram fetch failed for {channel}: {e}')
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')
        messages = soup.select('.tgme_widget_message_text')[-MESSAGES_PER_CHANNEL:]

        for msg in messages:
            text = msg.get_text(' ', strip=True)
            if not text:
                continue

            tickers = extract_tickers(text.upper())
            if not tickers:
                continue

            sentiment = calc_sentiment(text)
            for ticker in tickers:
                mentions.append({
                    'ticker': ticker,
                    'trend_text': text[:200],
                    'source': 'telegram',
                    'sentiment': sentiment,
                    'channel': channel,
                })

    return mentions


if __name__ == '__main__':
    import json
    channels = get_configured_channels()
    if not channels:
        print('No TELEGRAM_CHANNELS configured — set it in .env, comma-separated, no @.')
    else:
        print(json.dumps(scrape_telegram_channels(channels), indent=2))
