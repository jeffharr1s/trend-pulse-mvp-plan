"""
TrendPulse API - /api/alert
Sends alerts via Discord webhook and/or Resend email.

POST /api/alert
{
  "ticker": "$NVDA",
  "signal": "BUY",
  "momentum": 85,
  "sentiment": 0.45,
  "channels": ["discord", "email"]  // optional, defaults to all configured
}
"""

import os
import json
import html
from datetime import datetime
from http.server import BaseHTTPRequestHandler
import requests

from _logging_setup import get_logger

log = get_logger('api')


# ============================================================================
# Alert Senders
# ============================================================================

def send_discord(ticker: str, signal: str, momentum: int, sentiment: float, source: str = "reddit") -> bool:
    """Send alert to Discord webhook."""
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        return False
    
    # Color based on signal
    colors = {
        'BUY': 0x22c55e,   # green
        'SELL': 0xef4444,  # red
        'WATCH': 0xf59e0b, # yellow
        'HOLD': 0x6b7280   # gray
    }
    
    # Emoji
    emojis = {
        'BUY': '🟢',
        'SELL': '🔴', 
        'WATCH': '🟡',
        'HOLD': '⚪'
    }
    
    embed = {
        "title": f"{emojis.get(signal, '📊')} {signal} Signal: {ticker}",
        "color": colors.get(signal, 0x3b82f6),
        "fields": [
            {"name": "Momentum", "value": f"{momentum}/100", "inline": True},
            {"name": "Sentiment", "value": f"{'+' if sentiment > 0 else ''}{int(sentiment * 100)}%", "inline": True},
            {"name": "Source", "value": source.capitalize(), "inline": True},
        ],
        "footer": {"text": "TrendPulse • Not financial advice"},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    payload = {"embeds": [embed]}
    
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 204
    except Exception as e:
        log.error(f"Discord send failed: {e}")
        return False


def send_email(ticker: str, signal: str, momentum: int, sentiment: float, source: str = "reddit") -> bool:
    """Send alert via Resend email API."""
    api_key = os.environ.get('RESEND_API_KEY')
    to_email = os.environ.get('ALERT_EMAIL')
    
    if not api_key or not to_email:
        return False
    
    sentiment_str = f"{'+' if sentiment > 0 else ''}{int(sentiment * 100)}%"
    safe_ticker = html.escape(str(ticker))
    safe_signal = html.escape(str(signal))
    safe_source = html.escape(str(source).capitalize())

    email_html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 400px; margin: 0 auto; padding: 20px;">
      <h2 style="color: {'#22c55e' if signal == 'BUY' else '#ef4444' if signal == 'SELL' else '#f59e0b'};">
        {safe_signal} Signal: {safe_ticker}
      </h2>
      <table style="width: 100%; border-collapse: collapse;">
        <tr><td style="padding: 8px 0; border-bottom: 1px solid #eee;"><b>Momentum</b></td><td>{momentum}/100</td></tr>
        <tr><td style="padding: 8px 0; border-bottom: 1px solid #eee;"><b>Sentiment</b></td><td>{sentiment_str}</td></tr>
        <tr><td style="padding: 8px 0;"><b>Source</b></td><td>{safe_source}</td></tr>
      </table>
      <p style="color: #666; font-size: 12px; margin-top: 20px;">TrendPulse • Not financial advice</p>
    </div>
    """

    payload = {
        "from": "TrendPulse <alerts@resend.dev>",
        "to": [to_email],
        "subject": f"🚨 {safe_signal}: {safe_ticker} (Momentum {momentum})",
        "html": email_html
    }
    
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        log.error(f"Email send failed: {e}")
        return False


# ============================================================================
# Alert Logic
# ============================================================================

def should_alert(signal: str, momentum: int) -> bool:
    """Determine if this signal warrants an alert."""
    # Only alert on actionable signals with strong momentum
    if signal == 'BUY' and momentum >= 70:
        return True
    if signal == 'SELL' and momentum <= 30:
        return True
    if signal == 'WATCH' and momentum >= 80:  # Very high momentum watch
        return True
    return False


def determine_signal(momentum: int, sentiment: float) -> str:
    """Determine signal from momentum and sentiment."""
    if momentum >= 70 and sentiment > 0.2:
        return 'BUY'
    if momentum <= 30 or sentiment < -0.3:
        return 'SELL'
    if momentum >= 50 and sentiment > 0:
        return 'WATCH'
    return 'HOLD'


# ============================================================================
# Handler
# ============================================================================

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Parse body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}
            
            ticker = str(data.get('ticker', 'UNKNOWN'))[:20]
            source = str(data.get('source', 'reddit'))[:20]
            channels = data.get('channels', ['discord', 'email'])

            try:
                momentum = max(0, min(100, int(data.get('momentum', 50))))
            except (TypeError, ValueError):
                momentum = 50

            try:
                sentiment = max(-1.0, min(1.0, float(data.get('sentiment', 0))))
            except (TypeError, ValueError):
                sentiment = 0.0

            # Determine signal if not provided
            signal = data.get('signal') or determine_signal(momentum, sentiment)
            if signal not in ('BUY', 'SELL', 'WATCH', 'HOLD'):
                signal = determine_signal(momentum, sentiment)
            
            # Check if should alert
            if not should_alert(signal, momentum):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'sent': False,
                    'reason': 'Below alert threshold'
                }).encode())
                return
            
            # Send alerts
            results = {}
            
            if 'discord' in channels:
                results['discord'] = send_discord(ticker, signal, momentum, sentiment, source)
            
            if 'email' in channels:
                results['email'] = send_email(ticker, signal, momentum, sentiment, source)

            log.info(f"Alert sent: {ticker} {signal} momentum={momentum} channels={results}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'sent': True,
                'ticker': ticker,
                'signal': signal,
                'channels': results
            }).encode())
            
        except Exception as e:
            log.exception('do_POST failed')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
