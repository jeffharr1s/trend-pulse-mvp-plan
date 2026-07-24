"""
TrendPulse API - /api/trends
Serves the latest cached scan written by scraper/run_scraper.py.

Scraping itself doesn't happen here: it now drives a real logged-in
Reddit/X browser session (scraper/run_scraper.py, Playwright), which is
too slow/stateful to run inside a request/response cycle. This handler
just reads the last result the scraper wrote to data/latest_trends.json.
"""

import json
import os
from http.server import BaseHTTPRequestHandler

from _logging_setup import get_logger

log = get_logger('api')

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'latest_trends.json'
)


def load_latest_trends() -> dict:
    """Read the scraper's last cached output, or an empty placeholder if none exists yet."""
    if not os.path.exists(DATA_FILE):
        return {
            'trends': [],
            'updated': None,
            'sources': {'reddit': 0, 'twitter': 0},
            'warning': 'No scan data yet — start scraper/run_scraper.py first.'
        }

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error(f'Could not read {DATA_FILE}: {e}')
        return {
            'trends': [],
            'updated': None,
            'sources': {'reddit': 0, 'twitter': 0},
            'warning': f'Could not read scan data: {e}'
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = load_latest_trends()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        except Exception as e:
            log.exception('do_GET failed')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()
