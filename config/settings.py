"""
Configuration settings for the Coventry University Research Publications Crawler.
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# URLs
SEED_URL = "https://pureportal.coventry.ac.uk/en/organisations/fbl-school-of-economics-finance-and-accounting/publications/?page=0"
BASE_URL = "https://pureportal.coventry.ac.uk"

# Crawling settings
DELAY_BETWEEN_PAGES = 3  # seconds
DELAY_BETWEEN_REQUESTS = 1  # seconds
MAX_RETRIES = 3
TIMEOUT = 30  # seconds

# User agent
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# File paths
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
LOG_FILE = LOG_DIR / "crawler.log"
OUTPUT_FILE = DATA_DIR / "publications.csv"

# Ensure directories exist
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Selenium settings
HEADLESS = True  # Set to False for debugging
WINDOW_SIZE = (1920, 1080)

# Logging settings
LOG_LEVEL = "INFO"
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"

# CSV settings
CSV_ENCODING = "utf-8"
CSV_DELIMITER = ","

# Publication extraction settings
PUBLICATION_SELECTORS = {
    "publication_container": "div.result-container",
    "title": "h3.title a",
    "authors": "div.rendering.person, div.rendering.person a, span.rendering.person",
    "year": "span.date, div.date",
    "publication_link": "h3.title a",
    "author_link": "div.rendering.person a, span.rendering.person a"
}

# Pagination settings
PAGINATION_SELECTOR = "ul.pager li a"
NEXT_PAGE_SELECTOR = "a[rel='next']"
LAST_PAGE_SELECTOR = "ul.pager li:last-child a"

# Error handling
MAX_CONSECUTIVE_ERRORS = 5
ERROR_DELAY = 10  # seconds
