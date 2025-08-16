"""
Utility functions for the crawler.
"""

import csv
import time
import json
import requests
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger
import pandas as pd

from config.settings import LOG_FILE, LOG_FORMAT, LOG_LEVEL, CSV_ENCODING, CSV_DELIMITER, API_ENDPOINT, API_TIMEOUT, API_RETRIES


def setup_logging():
    """Setup logging configuration."""
    # Remove default handler
    logger.remove()
    
    # Add file handler
    logger.add(
        LOG_FILE,
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    # Add console handler
    logger.add(
        lambda msg: print(msg, end=""),
        format=LOG_FORMAT,
        level=LOG_LEVEL
    )


def delay(seconds: float):
    """Add delay between requests to be polite to the server."""
    logger.debug(f"Delaying for {seconds} seconds")
    time.sleep(seconds)


def send_to_api(data: List[Dict[str, Any]]) -> bool:
    """Send extracted data to API endpoint."""
    if not data:
        logger.warning("No data to send to API")
        return False
    
    # Prepare payload
    payload = {
        "publications": data
    }
    

    
    for attempt in range(API_RETRIES):
        try:
            logger.info(f"Sending {len(data)} publications to API (attempt {attempt + 1}/{API_RETRIES})")
            
            response = requests.post(
                API_ENDPOINT,
                json=payload,
                timeout=API_TIMEOUT,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Coventry-Crawler/1.0'
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent {len(data)} publications to API")
                return True
            else:
                logger.warning(f"API returned status code {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.error(f"API request timeout on attempt {attempt + 1}")
        except requests.exceptions.ConnectionError:
            logger.error(f"API connection error on attempt {attempt + 1}")
        except Exception as e:
            logger.error(f"API request error on attempt {attempt + 1}: {e}")
        
        if attempt < API_RETRIES - 1:
            logger.info(f"Retrying API call in 5 seconds...")
            time.sleep(5)
    
    logger.error(f"Failed to send data to API after {API_RETRIES} attempts")
    return False


def save_to_csv(data: List[Dict[str, Any]], output_file: Path):
    """Save extracted data to CSV file (fallback method)."""
    if not data:
        logger.warning("No data to save")
        return
    
    try:
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Save to CSV
        df.to_csv(
            output_file,
            index=False,
            encoding=CSV_ENCODING,
            sep=CSV_DELIMITER
        )
        
        logger.info(f"Saved {len(data)} publications to {output_file}")
        
    except Exception as e:
        logger.error(f"Error saving data to CSV: {e}")
        raise


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    cleaned = " ".join(text.strip().split())
    return cleaned


def extract_year_from_text(text: str) -> str:
    """Extract year from text string."""
    if not text:
        return ""
    
    import re
    # Look for 4-digit year pattern
    year_match = re.search(r'\b(19|20)\d{2}\b', text)
    if year_match:
        return year_match.group()
    return ""


def validate_url(url: str) -> bool:
    """Validate if URL is properly formatted."""
    if not url:
        return False
    
    return url.startswith(('http://', 'https://'))


def get_page_number_from_url(url: str) -> int:
    """Extract page number from URL."""
    import re
    match = re.search(r'page=(\d+)', url)
    if match:
        return int(match.group(1))
    return 0


def format_author_links(author_links: List[str]) -> str:
    """Format author links as comma-separated string."""
    if not author_links:
        return ""
    
    # Filter out empty links and join
    valid_links = [link for link in author_links if link.strip()]
    return ", ".join(valid_links)


def format_authors(authors: List[str]) -> str:
    """Format author names as comma-separated string."""
    if not authors:
        return ""
    
    # Clean and filter author names
    clean_authors = [clean_text(author) for author in authors if clean_text(author)]
    return ", ".join(clean_authors)


def create_backup_file(file_path: Path):
    """Create a backup of existing file if it exists."""
    if file_path.exists():
        backup_path = file_path.with_suffix(f'.backup_{int(time.time())}.csv')
        try:
            file_path.rename(backup_path)
            logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")


def get_crawling_statistics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate crawling statistics."""
    if not data:
        return {
            "total_publications": 0,
            "unique_authors": 0,
            "year_range": "",
            "pages_crawled": 0
        }
    
    # Count total publications
    total_publications = len(data)
    
    # Count unique authors
    all_authors = []
    for pub in data:
        authors = pub.get("authors", "").split(", ")
        all_authors.extend([author.strip() for author in authors if author.strip()])
    
    unique_authors = len(set(all_authors))
    
    # Get year range
    years = [pub.get("year", "") for pub in data if pub.get("year")]
    year_range = f"{min(years)} - {max(years)}" if years else ""
    
    # Count pages crawled
    pages = set(pub.get("page_number", 0) for pub in data)
    pages_crawled = len(pages)
    
    return {
        "total_publications": total_publications,
        "unique_authors": unique_authors,
        "year_range": year_range,
        "pages_crawled": pages_crawled
    }
