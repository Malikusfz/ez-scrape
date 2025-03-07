import os
import csv
import socket
from io import BytesIO
from warcio.warcwriter import WARCWriter
from warcio.statusandheaders import StatusAndHeaders
import logging
import aiohttp
import socket
import os
import asyncio
import uuid
from datetime import datetime
import csv
import time
import random
from aiohttp import ClientTimeout
from typing import List, Optional

class WarcScraper:
    def __init__(self, project_folder, log_callback=None):
        """
        Initialize the WARC scraper with project folder setup and logging.
        """
        self.project_folder = project_folder
        self.log_callback = log_callback or (lambda msg: None)
        
        # Configure retry settings
        self.max_retries = 3
        self.retry_delay = 5  # Base delay in seconds
        self.timeout = ClientTimeout(total=30)  # 30 seconds timeout
        
        # Rotating User Agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59"
        ]

        # Directories for output
        self.logs_folder = os.path.join(self.project_folder, "warcs", "logs")
        self.warcs_folder = os.path.join(self.project_folder, "warcs", "scraped-warcs")

        os.makedirs(self.logs_folder, exist_ok=True)
        os.makedirs(self.warcs_folder, exist_ok=True)

        # Configure explicit logger
        self.logger = logging.getLogger("WarcScraper")
        self.logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if not self.logger.handlers:
            log_file = os.path.join(self.logs_folder, "warc_scraping.log")
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(file_handler)

        # Next button configuration
        self.check_next_button = False
        self.next_button_selector = None

    def _log(self, message):
        """
        Log messages to file and optional callback.
        """
        self.logger.info(message)
        self.log_callback(message)

    def _get_random_headers(self) -> dict:
        """Generate random headers for requests."""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }

    async def _fetch_with_retry(self, session: aiohttp.ClientSession, url: str, attempt: int = 1) -> tuple[str, int]:
        """
        Fetch URL content with retry mechanism and proper error handling.
        Returns tuple of (content, status_code)
        """
        try:
            headers = self._get_random_headers()
            async with session.get(url, headers=headers, ssl=False, timeout=self.timeout) as response:
                if response.status == 403:
                    if attempt <= self.max_retries:
                        delay = self.retry_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                        self._log(f"Received 403 for {url}. Retrying in {delay:.2f} seconds (attempt {attempt}/{self.max_retries})")
                        await asyncio.sleep(delay)
                        return await self._fetch_with_retry(session, url, attempt + 1)
                    else:
                        raise aiohttp.ClientError(f"Max retries reached for {url}")
                
                return await response.text(), response.status
                
        except asyncio.TimeoutError:
            if attempt <= self.max_retries:
                delay = self.retry_delay * (2 ** (attempt - 1))
                self._log(f"Timeout for {url}. Retrying in {delay} seconds")
                await asyncio.sleep(delay)
                return await self._fetch_with_retry(session, url, attempt + 1)
            raise
        except (aiohttp.ClientError, Exception) as e:
            if attempt <= self.max_retries:
                delay = self.retry_delay * (2 ** (attempt - 1))
                self._log(f"Error fetching {url}: {str(e)}. Retrying in {delay} seconds")
                await asyncio.sleep(delay)
                return await self._fetch_with_retry(session, url, attempt + 1)
            raise

    def scrape_csv(self, csv_path, update_progress=None):
        """
        Scrape URLs from a CSV file and save them as WARC files.
        """
        try:
            with open(csv_path, "r") as f:
                reader = csv.reader(f)
                next(reader)  # Skip the header
                link_list = [row[0] for row in reader]
            self._log(f"Starting scraping for CSV: {csv_path}")
            # self.scrape_from_list(link_list, update_progress)
            asyncio.run(self.crawl_and_save_to_warc(link_list,self.warcs_folder,update_progress))
            self._log(f"Completed scraping for CSV: {csv_path}")

        except Exception as e:
            self._log(f"Error processing CSV {csv_path}: {e}")


    def _extract_page_links(self, soup, base_url):
        """
        Extract pagination links from the page-links div container.
        """
        page_links = []
        page_links_div = soup.find('div', class_='page-links')
        if page_links_div:
            for link in page_links_div.find_all('a', class_='post-page-numbers'):
                href = link.get('href')
                if href:
                    page_links.append(href)
        return page_links

    async def crawl_and_save_to_warc(self, links, warc_folder, update_progress=None, next_button_selector=None):
        # Common next page button selectors - Enhanced with JavaScript and AJAX patterns
        common_next_selectors = [
            # Standard navigation elements
            'a.next', 'a.pagination-next', 'a[rel="next"]',
            'a:contains("Next")', 'a:contains("next")',
            'button.next', 'button:contains("Next")',
            '.pagination .next', '.pagination-next',
            'nav.pagination a[aria-label="Next"]',
            
            # JavaScript/AJAX specific selectors
            '[data-page="next"]', '[data-action="next"]',
            '[data-role="next"]', '[data-nav="next"]',
            '.load-more', '#loadMore', '#load-more',
            '.show-more', '#showMore', '#show-more',
            '[data-load-more]', '[data-show-more]',
            
            # Common class patterns
            '.next-page', '.nextPage', '.next_page',
            '.pagination-next', '.paginationNext',
            '.pagination__next', '.pagination-item--next',
            
            # Semantic selectors
            '[aria-label*="Next"]', '[title*="Next"]',
            '[aria-label*="next"]', '[title*="next"]',
            
            # Icon-based navigation
            '.fa-chevron-right', '.fa-arrow-right',
            '.icon-next', '.icon-arrow-right'
        ]
        
        os.makedirs(warc_folder, exist_ok=True)
        total_links=len(links)
        async with aiohttp.ClientSession() as session:
            for idx, url in enumerate(links, start=1):
                try:
                    current_url = url
                    page_num = 1
                    all_content = []
                    
                    while True:
                        response_text, status = await self._fetch_with_retry(session, current_url)
                        all_content.append(response_text)
                        
                        # Skip next page checking if disabled
                        if not self.check_next_button:
                            break
                            
                        # Try to find next page links
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(response_text, 'html.parser')
                            
                        # First try to extract page links from page-links container
                        page_links = self._extract_page_links(soup, current_url)
                        if page_links:
                            # Get the next page URL based on current page number
                            if page_num < len(page_links):
                                next_url = page_links[page_num]
                                current_url = next_url
                                page_num += 1
                                if update_progress:
                                    update_progress(idx, len(links), f"Processing {url} - Page {page_num}")
                                continue
                            
                        # If no page-links found and next button checking is enabled, try other methods
                        if self.check_next_button:
                            next_link = None
                                
                            # Try user-provided selector first
                            if self.next_button_selector:
                                next_link = soup.select_one(self.next_button_selector)
                                
                            # Then try common selectors
                            if not next_link:
                                common_next_selectors = [
                                    # Standard navigation elements
                                    'a.next', 'a.pagination-next', 'a[rel="next"]',
                                    'a:contains("Next")', 'a:contains("next")',
                                    'button.next', 'button:contains("Next")',
                                    '.pagination .next', '.pagination-next',
                                    'nav.pagination a[aria-label="Next"]',
                                    
                                    # JavaScript/AJAX specific selectors
                                    '[data-page="next"]', '[data-action="next"]',
                                    '[data-role="next"]', '[data-nav="next"]',
                                    '.load-more', '#loadMore', '#load-more',
                                    '.show-more', '#showMore', '#show-more',
                                    '[data-load-more]', '[data-show-more]',
                                    
                                    # Common class patterns
                                    '.next-page', '.nextPage', '.next_page',
                                    '.pagination-next', '.paginationNext',
                                    '.pagination__next', '.pagination-item--next',
                                    
                                    # Semantic selectors
                                    '[aria-label*="Next"]', '[title*="Next"]',
                                    '[aria-label*="next"]', '[title*="next"]',
                                    
                                    # Icon-based navigation
                                    '.fa-chevron-right', '.fa-arrow-right',
                                    '.icon-next', '.icon-arrow-right'
                                ]
                                
                                for selector in common_next_selectors:
                                    elements = soup.select(selector)
                                    for element in elements:
                                        if element.get('onclick') or element.get('data-url') or \
                                            element.get('href') or element.get('data-href'):
                                            next_link = element
                                            break
                                    if next_link:
                                        break
                                
                            # Extract the next URL from various attributes
                            next_url = None
                            if next_link:
                                # Try to get URL from common attributes
                                next_url = next_link.get('data-url') or \
                                            next_link.get('data-href') or \
                                            next_link.get('href')
                                    
                                # Handle onclick JavaScript handlers
                                if not next_url and next_link.get('onclick'):
                                    onclick = next_link['onclick']
                                    # Extract URL from common JavaScript patterns
                                    import re
                                    url_patterns = [
                                        r"window\.location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",
                                        r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
                                        r"navigate\(['\"]([^'\"]+)['\"]",
                                        r"goToPage\(['\"]([^'\"]+)['\"]"
                                    ]
                                    for pattern in url_patterns:
                                        match = re.search(pattern, onclick)
                                        if match:
                                            next_url = next(filter(None, match.groups()), None)
                                            break
                                
                            if next_url:
                                # Handle relative URLs
                                if not next_url.startswith('http'):
                                    from urllib.parse import urljoin
                                    next_url = urljoin(current_url, next_url)
                                    
                                current_url = next_url
                                page_num += 1
                                if update_progress:
                                    update_progress(idx, total_links, f"Processing {url} - Page {page_num}")
                                continue
                                
                        break
                    
                    # Combine all content for the main URL
                    combined_content = '\n'.join(all_content)
                    ip_address = socket.gethostbyname(url.split("/")[2])

                    # Sanitize the URL for file naming
                    sanitized_url = url.removesuffix("/").split("/")[-1].replace(".html", "").replace("/", "_").replace(":", "_")
                    warc_file_path = os.path.join(warc_folder, f"{sanitized_url}.warc")

                    with open(warc_file_path, "wb") as f:
                            writer = WARCWriter(filebuf=f, gzip=False)

                            # Request record
                            request_headers = [
                                ("Host", url.split("/")[2]),
                                ("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/131.0.0.0 Safari/537.36"),
                                ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"),
                            ]
                            request_status_line = "GET / HTTP/1.1"
                            http_request_headers = StatusAndHeaders(request_status_line, request_headers, is_http_request=True)
                            request_payload = BytesIO()
                            request_record = writer.create_warc_record(url, "request", payload=request_payload, http_headers=http_request_headers)
                            request_record.rec_headers.add_header("WARC-IP-Address", ip_address)
                            writer.write_record(request_record)

                            # Response record
                            response_status_line = f"HTTP/1.1 {status} OK"
                            response_headers = [
                                ("Content-Type", "text/html"),
                                ("Server", "Unknown"),
                            ]
                            http_response_headers = StatusAndHeaders(response_status_line, response_headers)
                            response_payload = BytesIO(combined_content.encode("utf-8"))
                            response_record = writer.create_warc_record(url, "response", payload=response_payload, http_headers=http_response_headers)
                            response_record.rec_headers.add_header("WARC-Concurrent-To", request_record.rec_headers.get_header("WARC-Record-ID"))
                            response_record.rec_headers.add_header("WARC-IP-Address", ip_address)
                            writer.write_record(response_record)

                            # Metadata record
                            timestamp = datetime.now().isoformat() + "Z"
                            metadata_content = f"URL: {url}\nTimestamp: {timestamp}\nContent-Length: {len(combined_content.encode('utf-8'))}\nPages Scraped: {page_num}\n"
                            metadata_payload = BytesIO(metadata_content.encode("utf-8"))
                            metadata_record = writer.create_warc_record(
                                f"urn:uuid:{str(uuid.uuid4())}",
                                "metadata",
                                payload=metadata_payload,
                                warc_content_type="application/warc-fields",
                            )
                            metadata_record.rec_headers.add_header("WARC-Concurrent-To", response_record.rec_headers.get_header("WARC-Record-ID"))
                            metadata_record.rec_headers.add_header("WARC-IP-Address", ip_address)
                            writer.write_record(metadata_record)

                    if update_progress:
                        update_progress(idx, total_links, f"Processed {idx}/{total_links}: {url}")

                    print(f"Saved WARC file for {url} at {warc_file_path}")
                except Exception as e:
                    print(f"Failed to fetch {url}: {e}")


