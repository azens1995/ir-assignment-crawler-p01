"""
Main crawler implementation using Selenium for Coventry University research publications.
"""

import time
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
from src.utils import delay, send_to_api, create_backup_file, get_crawling_statistics, save_to_csv, fetch_text_via_selenium
from config.settings import (
    SEED_URL, DELAY_BETWEEN_PAGES, DELAY_BETWEEN_REQUESTS, 
    MAX_RETRIES, TIMEOUT, USER_AGENT, HEADLESS, WINDOW_SIZE,
    MAX_CONSECUTIVE_ERRORS, ERROR_DELAY, DATA_DIR, PARALLEL_PARSE, PARSE_WORKERS
)

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
        # Dev-mode CSV saving flag
        self.save_csv_flag = save_csv
        # Always fetch robots.txt from the site's base URL
        self.robots = RobotsPolicy(ROBOTS_URL, ROBOTS_USER_AGENT)
        
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
            current_url = SEED_URL
            # One-time robots fetch
            self._ensure_robots_loaded()
            
            while current_url:
                try:
                    # Respect robots crawl-delay between page visits
                    self._delay_per_robots()
                    
                    # Respect robots disallow for this URL
                    if not self._respect_robots_or_skip(current_url):
                        logger.warning(f"Skipping disallowed URL by robots: {current_url}")
                        current_url = self.get_next_page_url()
                        self.current_page += 1
                        continue
                    
                    # Navigate to current page
                    if not self.navigate_to_page(current_url):
                        self.consecutive_errors += 1
                        logger.error(f"Failed to navigate to page {self.current_page + 1}")
                        
                        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            logger.error(f"Too many consecutive errors ({self.consecutive_errors}), stopping crawler")
                            break
                        
                        # Try to get next page URL anyway
                        current_url = self.get_next_page_url()
                        self.current_page += 1
                        continue
                    
                    # Extract publications from current page
                    publications = self.extract_publications_from_page(current_url)
                    # Optional: parallel post-processing of publication records (no extra network)
                    if PARALLEL_PARSE and publications:
                        def _identity(pub):
                            return pub
                        try:
                            with ThreadPoolExecutor(max_workers=PARSE_WORKERS) as executor:
                                futures = [executor.submit(_identity, pub) for pub in publications]
                                publications = [f.result() for f in as_completed(futures)]
                        except Exception as e:
                            logger.debug(f"Parallel parse post-process failed, continuing sequentially: {e}")
                    self.all_publications.extend(publications)
                    
                    # Send publications to API
                    if publications:
                        _api_t0 = _time.perf_counter()
                        api_success = send_to_api(publications)
                        _api_t1 = _time.perf_counter()
                        logger.info(f"API post time: {(_api_t1 - _api_t0):.2f}s for {len(publications)} records")
                        if not api_success:
                            logger.warning(f"Failed to send publications from page {self.current_page + 1} to API")
                    
                    # Get next page URL
                    current_url = self.get_next_page_url()
                    self.current_page += 1
                    
                except Exception as e:
                    logger.error(f"Error processing page {self.current_page + 1}: {e}")
                    self.consecutive_errors += 1
                    
                    if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(f"Too many consecutive errors ({self.consecutive_errors}), stopping crawler")
                        break
                    
                    # Try to continue with next page
                    current_url = self.get_next_page_url()
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
        try:
            logger.info("Starting Coventry University Publications Crawler")
            
            # Setup WebDriver
            self.setup_driver()
            
            # Crawl all pages
            self.crawl_all_pages()
            
            # Save results
            self.save_results()
            
            logger.info("Crawling process completed successfully")
            
        except Exception as e:
            logger.error(f"Crawling process failed: {e}")
            raise
        
        finally:
            # Always close the driver
            self.close_driver()
