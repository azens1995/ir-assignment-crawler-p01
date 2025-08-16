"""
HTML parsing utilities for extracting publication data.
"""

from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from loguru import logger

from src.utils import clean_text, extract_year_from_text, format_authors, format_author_links, validate_url, get_page_number_from_url
from config.settings import PUBLICATION_SELECTORS, BASE_URL


class PublicationParser:
    """Parser for extracting publication data from Pure Portal pages."""
    
    def __init__(self):
        self.selectors = PUBLICATION_SELECTORS
    
    def parse_publications_page(self, html_content: str, page_url: str) -> List[Dict[str, Any]]:
        """
        Parse a publications page and extract all publication data.
        
        Args:
            html_content: Raw HTML content of the page
            page_url: URL of the page being parsed
            
        Returns:
            List of publication dictionaries
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        publications: List[Dict[str, Any]] = []
        
        # Find all publication containers
        publication_containers = soup.select(self.selectors["publication_container"])
        
        if not publication_containers:
            logger.warning(f"No publication containers found on page: {page_url}")
            return publications
        
        logger.info(f"Found {len(publication_containers)} publications on page")
        
        page_number = get_page_number_from_url(page_url)
        
        for i, container in enumerate(publication_containers):
            try:
                # Show progress every 10 publications
                if (i + 1) % 10 == 0:
                    logger.info(f"Parsing publication {i + 1}/{len(publication_containers)}")
                
                publication_data = self._extract_publication_data(container, page_number)
                if publication_data:
                    publications.append(publication_data)
            except Exception as e:
                logger.error(f"Error parsing publication container {i + 1}: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(publications)} publications from page {page_number}")
        return publications
    
    def _extract_publication_data(self, container, page_number: int) -> Optional[Dict[str, Any]]:
        """
        Extract publication data from a single container.
        
        Args:
            container: BeautifulSoup element containing publication data
            page_number: Current page number
            
        Returns:
            Dictionary with publication data or None if extraction fails
        """
        try:
            # Extract title and publication link
            title_element = container.select_one(self.selectors["title"])
            if not title_element:
                logger.warning("No title element found in publication container")
                return None
            
            title = clean_text(title_element.get_text())
            publication_link = title_element.get('href', '')
            
            # Make publication link absolute if it's relative
            if publication_link and not publication_link.startswith('http'):
                publication_link = BASE_URL + publication_link
            
            # Extract authors and author links
            authors = []
            author_links = []
            
            # First, try to find author elements
            author_elements = container.select(self.selectors["authors"])
            for author_elem in author_elements:
                author_name = clean_text(author_elem.get_text())
                if author_name and author_name not in authors:
                    authors.append(author_name)
                
                # Extract author link - try multiple approaches
                author_link = ""
                
                # First, check if the author element itself is a link
                if author_elem.name == 'a':
                    author_link = author_elem.get('href', '')
                else:
                    # Look for nested link elements
                    author_link_elem = author_elem.select_one(self.selectors["author_link"])
                    if author_link_elem:
                        author_link = author_link_elem.get('href', '')
                
                if author_link and not author_link.startswith('http'):
                    author_link = BASE_URL + author_link
                if validate_url(author_link) and author_link not in author_links:
                    author_links.append(author_link)
            
            # If no authors found in elements, try to extract from text content
            if not authors:
                try:
                    # Get all text content and look for author patterns
                    container_text = container.get_text()
                    
                    # Simple approach: look for text before the first date
                    import re
                    
                    # Find the first date in the text
                    date_pattern = r'\d{1,2}\s+\w+\s+\d{4}'
                    date_match = re.search(date_pattern, container_text)
                    
                    if date_match:
                        # Get text before the date
                        before_date = container_text[:date_match.start()].strip()
                        
                        # Simple split by comma and clean
                        if before_date:
                            parts = before_date.split(',')
                            # Take the first few parts as potential authors
                            potential_authors = []
                            for part in parts[:3]:  # Limit to first 3 parts
                                cleaned = clean_text(part.strip())
                                if cleaned and len(cleaned) > 2:
                                    potential_authors.append(cleaned)
                            
                            if potential_authors:
                                authors = potential_authors
                                
                except Exception as e:
                    logger.debug(f"Error extracting authors from text: {e}")
                    authors = []
            
            # Extract year
            year_element = container.select_one(self.selectors["year"])
            year = ""
            if year_element:
                year_text = clean_text(year_element.get_text())
                year = extract_year_from_text(year_text)
            
            # If no year found in element, try to extract from text content
            if not year:
                container_text = container.get_text()
                import re
                # Look for date patterns like "11 Feb 2025"
                date_pattern = r'\d{1,2}\s+\w+\s+(\d{4})'
                match = re.search(date_pattern, container_text)
                if match:
                    year = match.group(1)
            
            # Validate year before creating publication data
            if not year or not year.isdigit():
                logger.warning(f"Publication missing valid year: '{year}', skipping")
                return None
            
            year_int = int(year)
            if year_int < 1900 or year_int > 2030:
                logger.warning(f"Publication year {year_int} out of valid range (1900-2030), skipping")
                return None
            
            # Validate publication link
            if not publication_link or not publication_link.startswith('http'):
                logger.warning(f"Publication missing valid publication_link: '{publication_link}', skipping")
                return None
            
            # Create publication data dictionary
            publication_data = {
                "title": title,
                "year": year_int,
                "authors": format_authors(authors),
                "publication_link": publication_link,
                "author_links": format_author_links(author_links),
                "page_number": page_number
            }
            
            # Validate that we have at least a title
            if not publication_data["title"]:
                logger.warning("Publication missing title, skipping")
                return None
            
            return publication_data
            
        except Exception as e:
            logger.error(f"Error extracting publication data: {e}")
            return None
    
    def get_total_pages(self, html_content: str) -> int:
        """
        Extract total number of pages from pagination.
        
        Args:
            html_content: Raw HTML content of the page
            
        Returns:
            Total number of pages
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for pagination in navigation elements
        nav_elements = soup.find_all('nav')
        for nav in nav_elements:
            nav_text = nav.get_text().strip()
            if 'Next' in nav_text:
                # Look for the highest page number in the navigation
                import re
                # Look for patterns like "12345678910..16Next ›"
                # Extract the last number before "Next"
                match = re.search(r'(\d+)\.\.(\d+).*Next', nav_text)
                if match:
                    last_page = int(match.group(2))
                    total_pages = last_page + 1  # +1 because pages are 0-indexed
                    logger.info(f"Found {total_pages} total pages from navigation pattern")
                    return total_pages
                
                # Fallback: look for any numbers and take the highest
                page_numbers = re.findall(r'\b(\d+)\b', nav_text)
                if page_numbers:
                    # Convert to integers and find the highest
                    page_nums = [int(num) for num in page_numbers if num.isdigit()]
                    if page_nums:
                        # Filter out obviously wrong numbers (like 123456789)
                        valid_pages = [num for num in page_nums if num <= 100]  # Reasonable page limit
                        if valid_pages:
                            total_pages = max(valid_pages) + 1  # +1 because pages are 0-indexed
                            logger.info(f"Found {total_pages} total pages from navigation")
                            return total_pages
        
        # Fallback: look for pagination elements
        pagination_elements = soup.select("ul.pager li a")
        
        if not pagination_elements:
            logger.warning("No pagination elements found")
            return 1
        
        # Extract page numbers from pagination
        page_numbers = []
        for elem in pagination_elements:
            try:
                href = elem.get('href', '')
                if 'page=' in href:
                    import re
                    match = re.search(r'page=(\d+)', href)
                    if match:
                        page_numbers.append(int(match.group(1)))
            except Exception as e:
                logger.debug(f"Error parsing pagination element: {e}")
                continue
        
        if page_numbers:
            total_pages = max(page_numbers) + 1  # +1 because pages are 0-indexed
            logger.info(f"Found {total_pages} total pages")
            return total_pages
        
        logger.warning("Could not determine total pages, assuming 1")
        return 1
    
    def get_next_page_url(self, html_content: str, current_url: str) -> Optional[str]:
        """
        Extract the next page URL from pagination.
        
        Args:
            html_content: Raw HTML content of the page
            current_url: Current page URL
            
        Returns:
            Next page URL or None if no next page
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for "Next ›" link in navigation
        nav_elements = soup.find_all('nav')
        for nav in nav_elements:
            nav_text = nav.get_text().strip()
            if 'Next' in nav_text:
                nav_links = nav.find_all('a', href=True)
                for link in nav_links:
                    text = link.get_text().strip()
                    if 'Next' in text:
                        next_url = link.get('href', '')
                        if next_url and not next_url.startswith('http'):
                            next_url = BASE_URL + next_url
                        logger.info(f"Found next page link: {next_url}")
                        return next_url
        
        # Alternative: construct next page URL based on current page
        current_page = get_page_number_from_url(current_url)
        next_page = current_page + 1
        
        # Check if we've reached the end (based on the debug output, there are 16 pages: 0-15)
        if current_page >= 15:  # Last page is 15 (0-indexed)
            logger.info(f"Reached last page ({current_page}), no more pages")
            return None
        
        # Construct next page URL
        next_url = current_url.replace(f'page={current_page}', f'page={next_page}')
        logger.info(f"Constructed next page URL: {next_url}")
        return next_url
    
    def validate_page_content(self, html_content: str) -> bool:
        """
        Validate that the page contains expected content.
        
        Args:
            html_content: Raw HTML content of the page
            
        Returns:
            True if page appears to be a valid publications page
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for publication containers
        publication_containers = soup.select(self.selectors["publication_container"])
        if publication_containers:
            return True
        
        # Check for pagination (might be last page with no results)
        pagination = soup.select("ul.pager")
        if pagination:
            return True
        
        # Check for "no results" message
        no_results = soup.find(text=lambda text: text and "no results" in text.lower())
        if no_results:
            logger.info("Page indicates no results found")
            return True
        
        logger.warning("Page does not appear to be a valid publications page")
        return False
