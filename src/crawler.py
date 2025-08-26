"""
Main crawler implementation using Selenium for Coventry University research publications.
"""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger

from src.parser import PublicationParser
from src.utils import delay, send_to_api, create_backup_file, get_crawling_statistics, save_to_csv, fetch_text_via_selenium, fetch_existing_publication_ids, send_single_to_api
from config.settings import (
    SEED_URL, DELAY_BETWEEN_PAGES, DELAY_BETWEEN_REQUESTS, 
    MAX_RETRIES, TIMEOUT, USER_AGENT, HEADLESS, WINDOW_SIZE,
    MAX_CONSECUTIVE_ERRORS, ERROR_DELAY, DATA_DIR, PARALLEL_PARSE, PARSE_WORKERS
)
from config.settings import API_POST_EACH_DETAIL

# robots
from src.utils import RobotsPolicy
from config.settings import RESPECT_ROBOTS, ROBOTS_USER_AGENT, ROBOTS_URL

# typing for queues
from queue import Queue
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time as _time


class CoventryPublicationsCrawler:
    """Main crawler for Coventry University research publications."""
    
    def __init__(self, save_csv: bool = False):
        self.driver = None
        self.parser = PublicationParser()
        self.all_publications: List[Dict[str, Any]] = []
        self.consecutive_errors = 0
        self.current_page = 0
        self.skipped_records: List[Dict[str, Any]] = []  # Keep track of skipped publications and reasons
        # Dev-mode CSV saving flag
        self.save_csv_flag = save_csv
        # Always fetch robots.txt from the site's base URL
        self.robots = RobotsPolicy(ROBOTS_URL, ROBOTS_USER_AGENT)
        
    def _normalize_query_url(self, url: str) -> str:
        """Ensure no trailing slash before a query string (…/path?page=1, not …/path/?page=1)."""
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            path = parsed.path
            if parsed.query and path.endswith('/'):
                path = path.rstrip('/')
            return urlunparse(parsed._replace(path=path))
        except Exception:
            # Fallback simple normalization
            return url.replace('/?', '?')

    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options."""
        try:
            chrome_options = Options()
            
            if HEADLESS:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument(f"--user-agent={USER_AGENT}")
            chrome_options.add_argument(f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-images")  # Speed up loading
            # chrome_options.add_argument("--disable-javascript")  # Disable JS if not needed
            
            # Setup ChromeDriver with proper path handling for macOS ARM64
            try:
                driver_path = ChromeDriverManager().install()
                logger.info(f"ChromeDriver path: {driver_path}")
                
                # For macOS ARM64, we need to find the actual chromedriver executable
                import os
                import platform
                
                if platform.system() == "Darwin" and platform.machine() == "arm64":
                    # Look for the actual chromedriver executable in the directory
                    driver_dir = os.path.dirname(driver_path)
                    possible_drivers = [
                        os.path.join(driver_dir, "chromedriver"),
                        os.path.join(driver_dir, "chromedriver-mac-arm64"),
                        os.path.join(driver_dir, "chromedriver-mac-x64")
                    ]
                    
                    for driver in possible_drivers:
                        if os.path.exists(driver) and os.access(driver, os.X_OK):
                            driver_path = driver
                            logger.info(f"Found executable ChromeDriver: {driver_path}")
                            break
                    else:
                        # If no executable found, try to make the original path executable
                        if os.path.exists(driver_path):
                            os.chmod(driver_path, 0o755)
                            logger.info(f"Made ChromeDriver executable: {driver_path}")
                
                service = Service(driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                
            except Exception as driver_error:
                logger.warning(f"ChromeDriverManager failed: {driver_error}")
                logger.info("Trying alternative ChromeDriver setup...")
                
                # Fallback: try to use system ChromeDriver
                try:
                    self.driver = webdriver.Chrome(options=chrome_options)
                except Exception as fallback_error:
                    logger.error(f"Fallback ChromeDriver also failed: {fallback_error}")
                    raise driver_error
            
            # Set page load timeout
            self.driver.set_page_load_timeout(TIMEOUT)
            
            logger.info("Chrome WebDriver setup completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {e}")
            raise
    
    def close_driver(self):
        """Close the WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
    
    def _respect_robots_or_skip(self, url: str) -> bool:
        """Check robots rules for the URL; returns True if allowed, False otherwise."""
        try:
            if not RESPECT_ROBOTS:
                return True
            allowed = self.robots.can_fetch(url)
            if not allowed:
                logger.warning(f"Blocked by robots.txt: {url}")
            return allowed
        except Exception as e:
            logger.warning(f"robots check failed for {url}: {e}")
            return True
    
    def _delay_per_robots(self):
        try:
            delay_seconds = self.robots.crawl_delay_seconds()
            logger.info(f"Respecting crawl-delay: {delay_seconds}s")
            delay(delay_seconds)
        except Exception:
            delay(DELAY_BETWEEN_PAGES)
    
    def navigate_to_page(self, url: str) -> bool:
        """
        Navigate to a specific URL with error handling and retries.
        
        Args:
            url: URL to navigate to
            
        Returns:
            True if navigation successful, False otherwise
        """
        if self.driver is None:
            logger.error("WebDriver not initialized")
            return False
        if not self._respect_robots_or_skip(url):
            return False
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Navigating to page {self.current_page + 1}: {url}")
                _t0 = _time.perf_counter()
                self.driver.get(url)
                
                # Wait for page to load
                WebDriverWait(self.driver, TIMEOUT).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                _t1 = _time.perf_counter()
                logger.info(f"Page load time: {(_t1 - _t0):.2f}s for {url}")
                
                # Additional delay to ensure page is fully loaded
                delay(2)
                
                # Validate page content
                page_source = self.driver.page_source
                if self.parser.validate_page_content(page_source):
                    self.consecutive_errors = 0  # Reset error counter
                    return True
                else:
                    logger.warning(f"Page content validation failed for: {url}")
                    return False
                    
            except TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1} for URL: {url}")
                if attempt < MAX_RETRIES - 1:
                    delay(ERROR_DELAY)
                    continue
                else:
                    logger.error(f"Failed to load page after {MAX_RETRIES} attempts: {url}")
                    return False
                    
            except WebDriverException as e:
                logger.error(f"WebDriver error on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    delay(ERROR_DELAY)
                    continue
                else:
                    return False
                    
            except Exception as e:
                logger.error(f"Unexpected error navigating to {url}: {e}")
                return False
        
        return False
    
    def extract_publications_from_page(self, url: str) -> List[Dict[str, Any]]:
        """
        Extract publications from the current page.
        
        Args:
            url: Current page URL
            
        Returns:
            List of publication dictionaries
        """
        if self.driver is None:
            logger.error("WebDriver not initialized")
            return []
        try:
            import threading
            import queue
            
            # Use a queue to get results from the parsing thread
            result_queue: Queue = queue.Queue()
            exception_queue: Queue = queue.Queue()
            
            def parse_with_timeout():
                try:
                    page_source = self.driver.page_source
                    publications = self.parser.parse_publications_page(page_source, url)
                    result_queue.put(publications)
                except Exception as e:
                    exception_queue.put(e)
            
            # Start parsing in a separate thread
            parse_thread = threading.Thread(target=parse_with_timeout)
            parse_thread.daemon = True
            parse_thread.start()
            
            # Wait for result with timeout (30 seconds)
            try:
                publications = result_queue.get(timeout=30)
                
                if publications:
                    logger.info(f"Extracted {len(publications)} publications from page {self.current_page + 1}")
                    return publications
                else:
                    logger.warning(f"No publications found on page {self.current_page + 1}")
                    return []
                    
            except queue.Empty:
                logger.error(f"Parsing timeout for page {self.current_page + 1}")
                return []
            except Exception as e:
                logger.error(f"Error in parsing thread: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting publications from page {self.current_page + 1}: {e}")
            return []
    
    def get_next_page_url(self) -> Optional[str]:
        """
        Get the URL for the next page.
        
        Returns:
            Next page URL or None if no next page
        """
        if self.driver is None:
            logger.error("WebDriver not initialized")
            return None
        try:
            page_source = self.driver.page_source
            current_url = self.driver.current_url
            next_url = self.parser.get_next_page_url(page_source, current_url)
            
            if next_url:
                logger.info(f"Next page URL found: {next_url}")
                # Check robots before returning
                if self._respect_robots_or_skip(next_url):
                    return next_url
                else:
                    logger.warning("Next page blocked by robots.txt; stopping crawl")
                    return None
            else:
                logger.info("No next page found - reached end of publications")
                return None
                
        except Exception as e:
            logger.error(f"Error getting next page URL: {e}")
            return None
    
    def process_publications_with_details(self, publications: List[Dict[str, Any]], current_page_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Process publications: check cache and crawl details for new ones.
        
        Args:
            publications: List of basic publication data from listing page
            
        Returns:
            List of processed publications (only new ones with enhanced details)
        """
        from src.utils import is_publication_exists
        
        process_start_time = _time.perf_counter()
        logger.info(f"Processing {len(publications)} publications for detail crawling...")
        
        processed_publications = []
        skipped_count = 0
        detail_crawl_count = 0
        total_detail_crawl_time = 0.0
        
        for i, publication in enumerate(publications):
            title = publication.get('title', '')
            publication_url = publication.get('publication_link', '')
            
            logger.debug(f"Processing publication {i+1}/{len(publications)}: {title[:50]}...")
            
            if not title:
                logger.warning("Skipping publication with no title")
                try:
                    self.skipped_records.append({
                        "reason": "missing_title",
                        "page_number": self.current_page,
                        "index_on_page": i + 1,
                        "title": title or "",
                        "publication_link": publication.get('publication_link', '') or ""
                    })
                except Exception:
                    pass
                continue
            
            # Check if publication already exists
            if is_publication_exists(title):
                logger.info(f"Skipping existing publication: {title}")
                skipped_count += 1
                try:
                    self.skipped_records.append({
                        "reason": "already_exists",
                        "page_number": self.current_page,
                        "index_on_page": i + 1,
                        "title": title,
                        "publication_link": publication_url or ""
                    })
                except Exception:
                    pass
                continue
            
            # Publication is new - crawl details
            logger.info(f"NEW PUBLICATION FOUND: {title}")
            if publication_url and publication_url.startswith('http'):
                detail_start_time = _time.perf_counter()
                enhanced_publication = self.crawl_publication_details(publication_url, publication)
                detail_end_time = _time.perf_counter()
                detail_crawl_time = detail_end_time - detail_start_time
                total_detail_crawl_time += detail_crawl_time
                detail_crawl_count += 1
                
                if enhanced_publication:
                    processed_publications.append(enhanced_publication)
                    logger.info(f"Successfully enhanced publication details in {detail_crawl_time:.2f}s: {title}")
                    # Test mode: send each detailed record to API immediately
                    if API_POST_EACH_DETAIL:
                        try:
                            logger.info("Posting single enhanced publication to API (test mode)...")
                            _api_t0 = _time.perf_counter()
                            send_single_to_api(enhanced_publication)
                            _api_t1 = _time.perf_counter()
                            logger.info(f"Single API post time: {(_api_t1 - _api_t0):.2f}s for: {title}")
                        except Exception as e:
                            logger.warning(f"Failed to post single enhanced publication for '{title}': {e}")
                else:
                    # If detail crawling fails, use basic data
                    logger.warning(f"Failed to crawl details for {title}, using basic data")
                    processed_publications.append(publication)
            else:
                logger.warning(f"No valid URL for publication {title}, using basic data")
                processed_publications.append(publication)
        
        process_end_time = _time.perf_counter()
        total_process_time = process_end_time - process_start_time
        
        # Log comprehensive summary
        logger.info("=" * 60)
        logger.info("PUBLICATION PROCESSING SUMMARY")
        logger.info("=" * 60)
        if current_page_number is not None:
            logger.info(f"Page Number: {current_page_number}")
        logger.info(f"Total publications processed: {len(publications)}")
        logger.info(f"Existing publications skipped: {skipped_count}")
        logger.info(f"New publications found: {len(processed_publications)}")
        logger.info(f"Detail pages crawled: {detail_crawl_count}")
        logger.info(f"Total processing time: {total_process_time:.2f}s")
        if detail_crawl_count > 0:
            logger.info(f"Total detail crawling time: {total_detail_crawl_time:.2f}s")
            logger.info(f"Average detail crawling time: {total_detail_crawl_time/detail_crawl_count:.2f}s per publication")
        logger.info("=" * 60)
        
        return processed_publications
    
    def crawl_publication_details(self, publication_url: str, basic_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crawl a single publication's detail page to extract abstract and detailed authors.
        
        Args:
            publication_url: URL of the publication detail page
            basic_data: Basic publication data from listing page
            
        Returns:
            Enhanced publication data or None if crawling fails
        """
        title = basic_data.get('title', 'Unknown')
        crawl_start_time = _time.perf_counter()
        
        logger.info(f"Starting detail crawl for: {title}")
        logger.info(f"Detail page URL: {publication_url}")
        
        if not publication_url or not publication_url.startswith('http'):
            logger.warning(f"Invalid publication URL: {publication_url}")
            return basic_data
        
        # Check robots.txt for this URL
        robots_check_start = _time.perf_counter()
        if not self._respect_robots_or_skip(publication_url):
            logger.warning(f"Publication URL blocked by robots.txt: {publication_url}")
            return basic_data
        robots_check_end = _time.perf_counter()
        logger.debug(f"Robots.txt check completed in {robots_check_end - robots_check_start:.3f}s")
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Detail crawl attempt {attempt + 1}/{MAX_RETRIES} for: {title}")
                
                # Add delay to respect robots.txt
                delay_start = _time.perf_counter()
                self._delay_per_robots()
                delay_end = _time.perf_counter()
                logger.debug(f"Robots crawl delay: {delay_end - delay_start:.2f}s")
                
                # Check if driver is available
                if self.driver is None:
                    logger.error("WebDriver not initialized for detail crawling")
                    return basic_data
                
                # Navigate to publication detail page
                logger.info(f"Navigating to detail page: {publication_url}")
                nav_start = _time.perf_counter()
                self.driver.get(publication_url)
                
                # Wait for page to load
                logger.debug("Waiting for detail page to load...")
                WebDriverWait(self.driver, TIMEOUT).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                nav_end = _time.perf_counter()
                page_load_time = nav_end - nav_start
                logger.info(f"Detail page loaded successfully in {page_load_time:.2f}s")
                
                # Additional delay to ensure page is fully loaded
                logger.debug("Additional page stabilization delay...")
                delay(1)
                
                # Get page source and parse details
                logger.info("Extracting abstract and detailed authors...")
                parse_start = _time.perf_counter()
                page_source = self.driver.page_source
                enhanced_data = self.parser.parse_publication_detail(page_source, publication_url, basic_data)
                parse_end = _time.perf_counter()
                parse_time = parse_end - parse_start
                
                # Log what was extracted
                abstract = enhanced_data.get('abstract', '')
                authors = enhanced_data.get('authors', '')
                
                logger.info(f"Detail parsing completed in {parse_time:.2f}s")
                logger.info(f"Abstract extracted: {'Yes' if abstract else 'No'} ({len(abstract)} chars)")
                logger.info(f"Authors extracted: {authors}")
                
                crawl_end_time = _time.perf_counter()
                total_crawl_time = crawl_end_time - crawl_start_time
                logger.info(f"Detail crawl completed successfully in {total_crawl_time:.2f}s total")
                
                return enhanced_data
                
            except TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1} for publication: {title}")
                logger.warning(f"URL: {publication_url}")
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Retrying in {ERROR_DELAY} seconds...")
                    delay(ERROR_DELAY)
                    continue
                else:
                    logger.error(f"Failed to load publication page after {MAX_RETRIES} attempts: {title}")
                    return basic_data
                    
            except WebDriverException as e:
                logger.error(f"WebDriver error on attempt {attempt + 1} for {title}: {e}")
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Retrying in {ERROR_DELAY} seconds...")
                    delay(ERROR_DELAY)
                    continue
                else:
                    logger.error(f"WebDriver failed permanently for: {title}")
                    return basic_data
                    
            except Exception as e:
                logger.error(f"Unexpected error crawling details for {title}: {e}")
                logger.error(f"URL: {publication_url}")
                return basic_data
        
        crawl_end_time = _time.perf_counter()
        total_crawl_time = crawl_end_time - crawl_start_time
        logger.warning(f"Detail crawl failed after all attempts in {total_crawl_time:.2f}s: {title}")
        return basic_data

    def _ensure_robots_loaded(self):
        """Fetch robots.txt via Selenium, parse and log content."""
        try:
            if not RESPECT_ROBOTS:
                return
            if not self.driver:
                return
            if self.robots._fetched and not self.robots._unavailable:
                return
            # Always fetch via Selenium per requirement (once)
            logger.info("Fetching robots.txt via Selenium")
            content = fetch_text_via_selenium(self.driver, ROBOTS_URL)
            if not content:
                logger.warning("robots.txt content empty via Selenium; using fallback delay")
                self.robots._fetched = True
                self.robots._unavailable = True
                return
            # Strip HTML if any and parse
            import re
            text = re.sub(r'<[^>]+>', '\n', content)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            from urllib import robotparser
            self.robots.parser = robotparser.RobotFileParser()
            self.robots.parser.parse(lines)
            self.robots.parser.set_url(ROBOTS_URL)
            self.robots._crawl_delay = self.robots.parser.crawl_delay(ROBOTS_USER_AGENT) or self.robots.parser.crawl_delay("*")
            self.robots._fetched = True
            self.robots._unavailable = False
            # Log robots content (truncated)
            snippet = text if len(text) <= 2000 else text[:2000] + "\n... (truncated)"
            logger.info(f"robots.txt content (via Selenium):\n{snippet}")
        except Exception as e:
            logger.warning(f"Failed to load robots.txt via Selenium: {e}")
            self.robots._fetched = True
            self.robots._unavailable = True
    
    def crawl_all_pages(self):
        """Crawl all publication pages starting from the seed URL."""
        try:
            logger.info("Starting to crawl all publication pages")
            
            # Start with seed URL
            current_url = self._normalize_query_url(SEED_URL)
            total_pages: Optional[int] = None
            total_pages_logged: bool = False
            # One-time robots fetch
            self._ensure_robots_loaded()
            
            while current_url:
                try:
                    # Respect robots crawl-delay between page visits
                    self._delay_per_robots()
                    
                    # Respect robots disallow for this URL
                    if not self._respect_robots_or_skip(current_url):
                        logger.warning(f"Skipping disallowed URL by robots: {current_url}")
                        # If disallowed, increment page index deterministically to continue iteration
                        try:
                            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                            from src.utils import get_page_number_from_url
                            idx = get_page_number_from_url(current_url)
                            next_idx = idx + 1
                            if total_pages is not None and next_idx >= total_pages:
                                current_url = None
                            else:
                                parsed = urlparse(current_url)
                                query = parse_qs(parsed.query)
                                query['page'] = [str(next_idx)]
                                new_query = urlencode({k: v[0] for k, v in query.items()})
                                current_url = urlunparse(parsed._replace(query=new_query))
                        except Exception:
                            current_url = None
                        self.current_page += 1
                        continue
                    
                    # Navigate to current listing page
                    # Always navigate using normalized URL
                    current_url = self._normalize_query_url(current_url)
                    if not self.navigate_to_page(current_url):
                        self.consecutive_errors += 1
                        logger.error(f"Failed to navigate to page {self.current_page + 1}")
                        
                        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            logger.error(f"Too many consecutive errors ({self.consecutive_errors}), stopping crawler")
                            break
                        
                        # Move to the next page deterministically without touching Selenium state
                        try:
                            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                            from src.utils import get_page_number_from_url
                            idx = get_page_number_from_url(current_url)
                            next_idx = idx + 1
                            if total_pages is not None and next_idx >= total_pages:
                                current_url = None
                            else:
                                parsed = urlparse(current_url)
                                query = parse_qs(parsed.query)
                                query['page'] = [str(next_idx)]
                                new_query = urlencode({k: v[0] for k, v in query.items()})
                                current_url = self._normalize_query_url(urlunparse(parsed._replace(query=new_query)))
                        except Exception:
                            current_url = None
                        self.current_page += 1
                        continue
                    
                    # Extract publications from current page
                    publications = self.extract_publications_from_page(current_url)
                    
                    if publications:
                        # Process publications: check cache and crawl details for new ones
                        processed_publications = self.process_publications_with_details(publications, current_page_number=self.current_page)
                        
                        # Optional: parallel post-processing of publication records (no extra network)
                        if PARALLEL_PARSE and processed_publications:
                            def _identity(pub):
                                return pub
                            try:
                                with ThreadPoolExecutor(max_workers=PARSE_WORKERS) as executor:
                                    futures = [executor.submit(_identity, pub) for pub in processed_publications]
                                    processed_publications = [f.result() for f in as_completed(futures)]
                            except Exception as e:
                                logger.debug(f"Parallel parse post-process failed, continuing sequentially: {e}")
                        
                        self.all_publications.extend(processed_publications)
                        
                        # Send publications to API (page-batch) only if not in test single-post mode
                        if processed_publications and not API_POST_EACH_DETAIL:
                            _api_t0 = _time.perf_counter()
                            api_success = send_to_api(processed_publications)
                            _api_t1 = _time.perf_counter()
                            logger.info(f"API post time: {(_api_t1 - _api_t0):.2f}s for {len(processed_publications)} records")
                            if not api_success:
                                logger.warning(f"Failed to send publications from page {self.current_page + 1} to API; attempting per-item retry with logging")
                                # Retry individually and log failures as skipped
                                for idx, pub in enumerate(processed_publications, start=1):
                                    try:
                                        single_ok = send_single_to_api(pub)
                                        if not single_ok:
                                            self.skipped_records.append({
                                                "reason": "api_send_failed",
                                                "page_number": self.current_page,
                                                "index_on_page": idx,
                                                "title": pub.get('title', ''),
                                                "publication_link": pub.get('publication_link', '') or ""
                                            })
                                    except Exception as e:
                                        logger.debug(f"Per-item API send raised exception: {e}")
                                        self.skipped_records.append({
                                            "reason": "api_send_exception",
                                            "page_number": self.current_page,
                                            "index_on_page": idx,
                                            "title": pub.get('title', ''),
                                            "publication_link": pub.get('publication_link', '') or ""
                                        })
                    
                    # After finishing this page, determine total pages once (from DOM) and iterate deterministically
                    try:
                        if total_pages is None and self.driver is not None:
                            page_source_for_pagination = self.driver.page_source
                            detected_total = self.parser.get_total_pages(page_source_for_pagination)
                            # Parser returns total pages in 1-indexed UI terms; convert to 0-indexed last index
                            if detected_total and detected_total > 0:
                                total_pages = detected_total  # keep as count
                                if not total_pages_logged:
                                    logger.info(f"Total pages detected on first crawl: {detected_total}")
                                    total_pages_logged = True
                                logger.info(f"Detected pagination range: first=0, last={detected_total - 1} (total {detected_total} pages)")
                    except Exception as e:
                        logger.debug(f"Failed to detect total pages: {e}")

                    # Compute next index and construct next URL
                    try:
                        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                        from src.utils import get_page_number_from_url
                        current_index = get_page_number_from_url(current_url)
                        next_index = current_index + 1
                        if total_pages is not None and next_index >= total_pages:
                            logger.info(f"Reached last page index {current_index}; stopping crawl")
                            current_url = None
                        else:
                            parsed = urlparse(current_url)
                            query = parse_qs(parsed.query)
                            query['page'] = [str(next_index)]
                            new_query = urlencode({k: v[0] for k, v in query.items()})
                            current_url = self._normalize_query_url(urlunparse(parsed._replace(query=new_query)))
                            logger.info(f"Advancing to page index {next_index}: {current_url}")
                    except Exception as e:
                        logger.warning(f"Failed to construct next page URL deterministically: {e}")
                        current_url = None
                    self.current_page += 1
                    
                except Exception as e:
                    logger.error(f"Error processing page {self.current_page + 1}: {e}")
                    self.consecutive_errors += 1
                    
                    if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(f"Too many consecutive errors ({self.consecutive_errors}), stopping crawler")
                        break
                    
                    # Try to continue with next page by incrementing page index
                    try:
                        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                        from src.utils import get_page_number_from_url
                        idx = get_page_number_from_url(current_url) if current_url else self.current_page
                        next_idx = idx + 1
                        if total_pages is not None and next_idx >= total_pages:
                            current_url = None
                        else:
                            parsed = urlparse(current_url) if current_url else urlparse(self._normalize_query_url(SEED_URL))
                            query = parse_qs(parsed.query)
                            query['page'] = [str(next_idx)]
                            new_query = urlencode({k: v[0] for k, v in query.items()})
                            current_url = self._normalize_query_url(urlunparse(parsed._replace(query=new_query)))
                    except Exception:
                        current_url = None
                    self.current_page += 1
                    continue
            
            logger.info(f"Crawling completed. Total pages crawled: {self.current_page}")
            logger.info(f"Total publications extracted: {len(self.all_publications)}")
            
        except Exception as e:
            logger.error(f"Error during crawling: {e}")
            raise
    
    def save_results(self):
        """Generate and log crawling statistics."""
        try:
            # Generate and log statistics
            stats = get_crawling_statistics(self.all_publications)
            logger.info("Crawling Statistics:")
            logger.info(f"  Total Publications: {stats['total_publications']}")
            logger.info(f"  Unique Authors: {stats['unique_authors']}")
            logger.info(f"  Year Range: {stats['year_range']}")
            logger.info(f"  Pages Crawled: {stats['pages_crawled']}")
            # Log skipped publications summary
            try:
                total_skipped = len(self.skipped_records)
                logger.info(f"  Publications Skipped (not recorded): {total_skipped}")
                if total_skipped > 0:
                    logger.info("  Skipped Publications Detail (up to first 20 shown):")
                    for rec in self.skipped_records[:20]:
                        logger.info(f"    - Page {rec.get('page_number')} idx {rec.get('index_on_page')}: '{rec.get('title','')}' reason={rec.get('reason')} link={rec.get('publication_link','')}")
                    # If there are more skipped, show a short summary count by reason
                    if total_skipped > 20:
                        reason_counts = {}
                        for rec in self.skipped_records:
                            reason = rec.get('reason', 'unknown')
                            reason_counts[reason] = reason_counts.get(reason, 0) + 1
                        logger.info("  Skipped counts by reason: " + ", ".join(f"{k}={v}" for k, v in reason_counts.items()))
            except Exception:
                logger.debug("Failed to render skipped publications summary")
            
            # Save to CSV in data directory only if dev flag is enabled
            if self.save_csv_flag and self.all_publications:
                output_file = Path(DATA_DIR) / "publications.csv"
                create_backup_file(output_file)
                save_to_csv(self.all_publications, output_file)
                logger.info(f"CSV saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Error generating statistics: {e}")
            raise
    
    def run(self):
        """Main method to run the complete crawling process."""
        start_time = datetime.now()
        start_timestamp = start_time.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            logger.info("=" * 60)
            logger.info("STARTING COVENTRY UNIVERSITY PUBLICATIONS CRAWLER")
            logger.info("=" * 60)
            logger.info(f"Start Time: {start_timestamp}")
            
            # Initialize publication ID cache
            logger.info("Initializing publication ID cache...")
            cache_start = time.perf_counter()
            fetch_existing_publication_ids()
            cache_end = time.perf_counter()
            logger.info(f"Cache initialization completed in {cache_end - cache_start:.2f} seconds")
            
            # Setup WebDriver
            logger.info("Setting up WebDriver...")
            driver_start = time.perf_counter()
            self.setup_driver()
            driver_end = time.perf_counter()
            logger.info(f"WebDriver setup completed in {driver_end - driver_start:.2f} seconds")
            
            # Crawl all pages
            logger.info("Starting page crawling...")
            crawl_start = time.perf_counter()
            self.crawl_all_pages()
            crawl_end = time.perf_counter()
            logger.info(f"Page crawling completed in {crawl_end - crawl_start:.2f} seconds")
            
            # Save results
            logger.info("Saving results...")
            save_start = time.perf_counter()
            self.save_results()
            save_end = time.perf_counter()
            logger.info(f"Results saving completed in {save_end - save_start:.2f} seconds")
            
            # Calculate total time
            end_time = datetime.now()
            end_timestamp = end_time.strftime("%Y-%m-%d %H:%M:%S")
            total_duration = end_time - start_time
            
            logger.info("=" * 60)
            logger.info("CRAWLING PROCESS COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info(f"End Time: {end_timestamp}")
            logger.info(f"Total Duration: {total_duration}")
            logger.info(f"Total Duration (seconds): {total_duration.total_seconds():.2f}")
            
            # Print summary to console
            print(f"\n{'='*60}")
            print(f"CRAWLING COMPLETED SUCCESSFULLY")
            print(f"{'='*60}")
            print(f"Start Time: {start_timestamp}")
            print(f"End Time: {end_timestamp}")
            print(f"Total Duration: {total_duration}")
            print(f"Total Duration (seconds): {total_duration.total_seconds():.2f}")
            print(f"{'='*60}")
            
        except Exception as e:
            end_time = datetime.now()
            end_timestamp = end_time.strftime("%Y-%m-%d %H:%M:%S")
            total_duration = end_time - start_time
            
            logger.error("=" * 60)
            logger.error("CRAWLING PROCESS FAILED")
            logger.error("=" * 60)
            logger.error(f"End Time: {end_timestamp}")
            logger.error(f"Duration before failure: {total_duration}")
            logger.error(f"Error: {e}")
            logger.error("=" * 60)
            
            print(f"\n{'='*60}")
            print(f"CRAWLING FAILED")
            print(f"{'='*60}")
            print(f"Start Time: {start_timestamp}")
            print(f"End Time: {end_timestamp}")
            print(f"Duration before failure: {total_duration}")
            print(f"Error: {e}")
            print(f"{'='*60}")
            
            raise
        
        finally:
            # Always close the driver
            self.close_driver()
