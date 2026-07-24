"""
Shared logging setup for the scraper and the local API handlers.

Writes rotating log files to logs/<name>.log and echoes to the console,
so "watch it happen live" and "grep an older run" both just work.

Never log secrets: only log env var *names* on failure (e.g. "RESEND_API_KEY
missing"), never values, and never full request/response bodies that might
carry a webhook URL or API key.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured — avoid duplicate handlers on re-import

    os.makedirs(LOGS_DIR, exist_ok=True)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s %(levelname)-7s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = RotatingFileHandler(
        os.path.join(LOGS_DIR, f'{name}.log'),
        maxBytes=2 * 1024 * 1024,  # 2MB per file
        backupCount=3,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger
