import os
import logging
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket

class PamekasanAPBDScraper:
    """
    Scraper for extracting APBD (budget) document links from Pamekasan Regency website.
    This scraper is designed to navigate through each year's budget documents and
    extract all relevant links.
    """
    
    def __init__(self, output_folder="output/Pamekasan Regency/APBD", log_callback=None):
        """
        Initialize the PamekasanAPBDScraper with WebDriver and configurations.
        
        Args:
            output_folder: Folder where links and downloaded files will be saved
            log_callback: Function to handle logging messages
        """
        self.base_url = "https://pamekasankab.go.id/apbd"
        self.output_folder = output_folder
        self.log_callback = log_callback or (lambda message: None)
        
        # Create output directory
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Create CSV file for storing links
        self.csv_path = os.path.join(self.output_folder, "apbd_links.csv")
        if not os.path.exists(self.csv_path):
            pd.DataFrame(columns=["year", "document_title", "link"]).to_csv(self.csv_path, index=False)
            
        # Initialize driver with error handling
        self.driver = None
        try:
            self.driver = self._setup_webdriver()
            self.wait = WebDriverWait(self.driver, 30)  # Increased from 20 to 30 seconds
        except Exception as e:
            self._log(f"Failed to initialize WebDriver: {e}")
            raise
    
    def _setup_webdriver(self):
        """
        Set up Chrome WebDriver with headless options and extended timeouts.
        """
        # Set default socket timeout
        socket.setdefaulttimeout(180)  # 3 minutes timeout
        
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--proxy-server='direct://'")
        options.add_argument("--proxy-bypass-list=*")
        
        # Disable loggings
        options.add_argument('--log-level=3')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        prefs = {
            "download.prompt_for_download": False,
            "download.default_directory": self.output_folder,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        options.add_experimental_option("prefs", prefs)
        
        # Initialize with retry mechanism
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self._log(f"Initializing Chrome WebDriver (attempt {attempt + 1}/{max_attempts})...")
                
                # Create a service with specific timeout settings
                service = Service(
                    ChromeDriverManager().install(),
                    service_args=['--verbose'], 
                    log_path=os.path.join(self.output_folder, 'chromedriver.log')
                )
                
                # Initialize the driver with service and options
                driver = webdriver.Chrome(service=service, options=options)
                
                # Set timeouts
                driver.set_page_load_timeout(180)  # 3 minutes for page load
                driver.set_script_timeout(180)  # 3 minutes for scripts
                
                # Test the driver with a simple operation
                driver.get("about:blank")
                
                self._log("Chrome WebDriver initialized successfully")
                return driver
                
            except Exception as e:
                self._log(f"WebDriver initialization failed (attempt {attempt + 1}/{max_attempts}): {e}")
                # Close any existing driver instance
                try:
                    if 'driver' in locals() and driver:
                        driver.quit()
                except Exception:
                    pass
                
                if attempt < max_attempts - 1:
                    self._log(f"Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    self._log("All WebDriver initialization attempts failed.")
                    raise
        
        raise RuntimeError("Failed to initialize WebDriver after multiple attempts")
    
    def _log(self, message):
        """Log messages through the callback."""
        logging.info(message)
        self.log_callback(message)
    
    def _get_year_options(self):
        """
        Extract all available year options from the APBD page with robust error handling.
        
        Returns:
            Dictionary mapping year names to their URLs
        """
        years_dict = {}
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                self._log(f"Loading base URL (attempt {retry_count + 1}/{max_retries})...")
                self.driver.get(self.base_url)
                self._log("Extracting available year options...")
                
                # Wait for the page to load and find year links in the tabs
                year_elements = self.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".nav.nav-tabs li a[href^='#tab']"))
                )
                
                for element in year_elements:
                    year_text = element.text.strip()
                    if year_text.startswith('TA '):  # "TA" prefix for fiscal year
                        year = year_text.replace('TA ', '')
                        tab_id = element.get_attribute("href").split('#')[-1]
                        if year and tab_id:
                            # Since tabs are in the same page, we'll use fragment identifiers
                            years_dict[year] = f"{self.base_url}#{tab_id}"
                
                if years_dict:
                    self._log(f"Found {len(years_dict)} year options: {', '.join(years_dict.keys())}")
                    return years_dict
                
                self._log("No year options found on the page.")
                return {}
                
            except (TimeoutException, WebDriverException) as e:
                retry_count += 1
                self._log(f"Error loading page (attempt {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    self._log("Maximum retries reached. Could not load year options.")
                    return {}
                time.sleep(5)  # Wait before retrying
        
        return {}
    
    def _extract_drive_file_id(self, preview_url):
        """
        Extract Google Drive file ID from preview URL.
        Example: https://drive.google.com/file/d/FILE_ID/preview -> FILE_ID
        """
        try:
            # Extract file ID from preview URL
            if "/file/d/" in preview_url and "/preview" in preview_url:
                file_id = preview_url.split("/file/d/")[1].split("/preview")[0]
                return file_id
            return None
        except Exception:
            return None
            
    def _get_direct_download_url(self, preview_url):
        """
        Convert Google Drive preview URL to direct download URL
        """
        file_id = self._extract_drive_file_id(preview_url)
        if (file_id):
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        return preview_url
    
    def _extract_documents_from_year(self, year, year_url):
        """
        Extract all document links from a specific year's page.
        
        Args:
            year: Year label (e.g., "2023")
            year_url: URL for the year's APBD page
            
        Returns:
            List of dictionaries containing document information
        """
        self._log(f"Processing documents for year: {year}")
        self.driver.get(year_url)
        
        try:
            # First, we need to click on the year tab to make it active
            tab_id = year_url.split('#')[-1]
            if tab_id.startswith('tab'):
                try:
                    # Find and click the tab with better waiting strategy
                    tab_selector = f".nav.nav-tabs li a[href='#{tab_id}']"
                    tab_element = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, tab_selector))
                    )
                    self._log(f"Clicking on tab: {tab_id}")
                    tab_element.click()
                    
                    # Wait longer for tab content to load and become visible
                    self._log("Waiting for tab content to load...")
                    
                    # Wait for the active tab to be visible
                    self.wait.until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, f"#{tab_id}.active"))
                    )
                    
                    # Wait for table to be fully loaded
                    self.wait.until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, f"#{tab_id}.active table.table-striped"))
                    )
                    
                    # Additional sleep to ensure dynamic content is fully loaded
                    time.sleep(5)
                    
                    self._log("Tab content loaded successfully")
                except Exception as e:
                    self._log(f"Error activating tab {tab_id}: {e}")
                    # Try to continue anyway
            
            # Find the active tab content
            try:
                active_tab = self.driver.find_element(By.CSS_SELECTOR, f"#{tab_id}.active")
            except:
                # Fallback to any active tab if specific tab selector fails
                active_tab = self.driver.find_element(By.CSS_SELECTOR, ".tab-content .tab-pane.active")
            
            # Find the table within the active tab
            table = active_tab.find_element(By.CSS_SELECTOR, "table")
            
            # Try to get all rows - first directly from tbody
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            
            # If no rows found, try a broader selector
            if not rows:
                self._log("No rows found with direct selector, trying alternative selector")
                rows = table.find_elements(By.TAG_NAME, "tr")
                # Remove header row if present
                if rows and "thead" in rows[0].get_attribute("outerHTML"):
                    rows = rows[1:]
            
            # Check if we found any rows
            if not rows:
                self._log("No document rows found in the table")
                # Try to get the HTML to see what's there
                table_html = table.get_attribute("outerHTML")
                self._log(f"Table HTML structure: {table_html[:500]}...")
            else:
                self._log(f"Found {len(rows)} table rows to process")
            
            documents = []
            for row in rows:
                try:
                    # Get all cells in this row
                    cells = row.find_elements(By.TAG_NAME, "td")
                    
                    # Skip rows without enough cells
                    if len(cells) < 2:
                        continue
                    
                    # The second cell (index 1) contains the document link
                    link_cell = cells[1]
                    
                    # Directly try to find the link element
                    try:
                        link_element = link_cell.find_element(By.TAG_NAME, "a")
                    except:
                        # If no direct link found, print the cell's HTML for debugging
                        self._log(f"Could not find link in cell: {link_cell.get_attribute('outerHTML')}")
                        continue
                    
                    title = link_element.text.strip()
                    
                    # Skip empty titles
                    if not title:
                        continue
                    
                    # Handle different types of links
                    link = None
                    onclick = link_element.get_attribute("onclick")
                    
                    if onclick and "myPdf" in onclick:
                        # Extract preview URL from onclick attribute
                        preview_url = onclick.split('myPdf("')[1].split('")')[0]
                        link = self._get_direct_download_url(preview_url)
                    else:
                        # For external links, use href directly
                        link = link_element.get_attribute("href")
                    
                    if title and link:
                        # Common document pattern for all years
                        base_titles = [
                            "Rencana Kerja Pemerintah Daerah",
                            "Kebijakan Umum Anggaran",
                            "Prioritas dan Plafon Anggaran",
                            "Rencana Kerja & Anggaran SKPD",
                            "Rencana Kerja & Anggaran PPKD",
                            "Rancangan Peraturan Daerah APBD",
                            "Peraturan Daerah APBD",
                            "Peraturan Bupati Penjabaran APBD",
                            "Dokumen Pelaksanaan Anggaran SKPD",
                            "Dokumen Pelaksanaan Anggaran PPKD",
                            "Realisasi Pendapatan Daerah",
                            "Realisasi Belanja Daerah",
                            "Realisasi Pembiayaan Daerah",
                            "Rancangan Perubahan APBD",
                            "Peraturan Daerah Perubahan APBD",
                            "Peraturan Bupati Penjabaran Perubahan APBD",
                            "Rencana Kerja dan Anggaran Perubahan APBD",
                            "Rencana Umum Pengadaan",
                            "SK Bupati Pejabat Pengelola Keuangan Daerah",
                            "Peraturan Bupati Kebijakan Akuntansi",
                            "Laporan Arus Kas",
                            "Laporan Realisasi Anggaran SKPD",
                            "Laporan Realisasi Anggaran PPKD",
                            "Neraca",
                            "Catatan atas Laporan Keuangan",
                            "Laporan Keuangan BUMD",
                            "Laporan Akuntabilitas dan Kinerja Pemerintah",
                            "Perda Pertanggungjawaban Pelaksanaan APBD",
                            "Opini BPK RI"
                        ]
                        
                        documents.append({
                            "year": year,
                            "document_title": title,
                            "link": link
                        })
                        
                except Exception as e:
                    self._log(f"Error extracting document from row: {e}")
            
            # If we found fewer than expected documents, try to clone the structure from 2023
            if len(documents) < 29 and year not in ["2023"]:
                self._log(f"Only found {len(documents)} for {year}, attempting to generate missing documents")
                
                # Read the CSV to get 2023 documents as templates
                try:
                    template_docs = []
                    if os.path.exists(self.csv_path):
                        df = pd.read_csv(self.csv_path)
                        if not df.empty:
                            template_df = df[df['year'] == '2023']
                            if not template_df.empty:
                                template_docs = template_df.to_dict('records')
                    
                    # If we have template documents, use them to estimate missing ones
                    if template_docs:
                        # Get document titles we already have
                        existing_titles = [doc['document_title'] for doc in documents]
                        
                        # For each template document, check if we're missing it
                        for template in template_docs:
                            template_title = template['document_title']
                            base_title = ' '.join(template_title.split(' ')[:-1])  # Remove year
                            current_title = f"{base_title} {year}"
                            
                            # If we don't have this document yet, add a note
                            if current_title not in existing_titles:
                                self._log(f"Missing document: {current_title}")
                except Exception as e:
                    self._log(f"Error analyzing missing documents: {e}")
            
            self._log(f"Found {len(documents)} documents for year {year}")
            return documents
        
        except Exception as e:
            self._log(f"Error processing year {year}: {e}")
            return []
    
    def _save_links_to_csv(self, documents):
        """Save document links to CSV file."""
        if not documents:
            return
            
        try:
            # Read existing links to avoid duplicates
            existing_df = pd.read_csv(self.csv_path) if os.path.exists(self.csv_path) else pd.DataFrame()
            
            # Create DataFrame from new documents
            new_df = pd.DataFrame(documents)
            
            # Combine and remove duplicates
            if not existing_df.empty:
                combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["link"])
                combined_df.to_csv(self.csv_path, index=False)
            else:
                new_df.to_csv(self.csv_path, index=False)
                
            self._log(f"Saved {len(documents)} document links to CSV")
        except Exception as e:
            self._log(f"Error saving links to CSV: {e}")
    
    def _setup_requests_session(self):
        """
        Set up a requests session with retry strategy.
        """
        session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def download_document(self, document):
        """
        Download a document file from the provided link.
        
        Args:
            document: Dictionary containing document information
        """
        try:
            year = str(document["year"])  # Convert year to string to avoid join() errors
            title = document["document_title"]
            url = document["link"]
            
            # Create year-specific folder
            year_folder = os.path.join(self.output_folder, year)
            os.makedirs(year_folder, exist_ok=True)
            
            # Clean filename
            safe_title = "".join([c if c.isalnum() or c in [' ', '.', '-', '_'] else '_' for c in title])
            
            # Determine file extension properly
            # For Google Drive links, use pdf extension
            if 'drive.google.com' in url or 'uc?export=download' in url:
                file_ext = 'pdf'
            elif url.startswith('http') and '.' in url.split('/')[-1]:
                # Try to get extension from URL file path
                file_ext = url.split('.')[-1].split('?')[0]
                # Make sure extension is valid and not too long
                if len(file_ext) > 5 or not file_ext.isalnum():
                    file_ext = 'pdf'
            else:
                # Default extension
                file_ext = 'pdf'
                
            filename = f"{safe_title}.{file_ext}"
            file_path = os.path.join(year_folder, filename)
            
            # Download if file doesn't exist
            if not os.path.exists(file_path):
                session = self._setup_requests_session()
                self._log(f"Downloading: {title} ({year})")
                
                # Set up headers to mimic browser behavior
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # Handle SSL issues
                verify = True
                try:
                    response = session.get(url, stream=True, timeout=180, headers=headers, verify=verify)
                    response.raise_for_status()
                except requests.exceptions.SSLError:
                    # If SSL verification fails, try without verification
                    self._log(f"SSL verification failed for {url}. Trying without verification...")
                    verify = False
                    response = session.get(url, stream=True, timeout=180, headers=headers, verify=verify)
                    response.raise_for_status()
                
                # Check for Google Drive warning page
                if 'confirmar?id=' in response.url:
                    # Handle Google Drive confirmation page
                    self._log(f"Handling Google Drive confirmation for: {title}")
                    confirm_token = response.cookies.get('download_warning')
                    if confirm_token:
                        url = f"{url}&confirm={confirm_token}"
                        response = session.get(url, stream=True, timeout=180, headers=headers, verify=verify)
                        response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                self._log(f"Successfully downloaded: {filename}")
            else:
                self._log(f"File already exists: {filename}")
        except Exception as e:
            self._log(f"Error downloading {title if 'title' in locals() else 'document'}: {e}")
            
    def download_all_documents(self, max_workers=5):
        """
        Download all documents found in the CSV.
        
        Args:
            max_workers: Maximum number of concurrent downloads
        """
        try:
            df = pd.read_csv(self.csv_path)
            documents = df.to_dict('records')
            
            self._log(f"Starting download of {len(documents)} documents...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(self.download_document, documents))
                
            self._log("All downloads completed!")
        except Exception as e:
            self._log(f"Error during batch download: {e}")
    
    def scrape(self):
        """
        Main scraping method to extract all APBD links from all available years.
        """
        all_documents = []
        
        try:
            if not self.driver:
                self._log("WebDriver is not initialized. Exiting.")
                return []
                
            # Get all available years
            years_dict = self._get_year_options()
            
            if not years_dict:
                self._log("No year options found. Exiting.")
                return []
                
            # Process each year
            for year, year_url in years_dict.items():
                documents = self._extract_documents_from_year(year, year_url)
                all_documents.extend(documents)
                time.sleep(1)  # Be polite to the server
                
            # Save all links to CSV
            self._log(f"Total documents found across all years: {len(all_documents)}")
            self._save_links_to_csv(all_documents)
            
        except Exception as e:
            self._log(f"Scraping process failed: {e}")
        finally:
            self.close()
            
        return all_documents
    
    def close(self):
        """Close the WebDriver safely."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self._log(f"Error closing WebDriver: {e}")


def scrape_pamekasan_apbd(download_files=False, max_workers=5, extract_gdrive_links=False):
    """
    Main function to start the Pamekasan APBD scraping process.
    
    Args:
        download_files: Whether to download the actual files after scraping links
        max_workers: Maximum number of concurrent downloads if downloading files
        extract_gdrive_links: Whether to extract Google Drive links to a separate CSV
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Create and run scraper
    scraper = PamekasanAPBDScraper()
    documents = scraper.scrape()
    
    # Extract Google Drive links if requested
    if extract_gdrive_links and documents:
        extract_google_drive_links(scraper.csv_path)
    
    # Download files if requested
    if download_files and documents:
        scraper = PamekasanAPBDScraper()  # Create a new instance for downloads
        scraper.download_all_documents(max_workers=max_workers)
        scraper.close()
        
    return documents

def extract_google_drive_links(csv_path):
    """
    Extract Google Drive links from CSV and save to a separate file.
    """
    try:
        output_folder = os.path.dirname(csv_path)
        gdrive_csv_path = os.path.join(output_folder, "gdrive_links.csv")
        
        # Read the original CSV
        df = pd.read_csv(csv_path)
        
        # Filter for Google Drive links
        gdrive_df = df[df['link'].str.contains('drive.google.com', case=False, na=False)]
        
        # Save to new CSV
        if not gdrive_df.empty:
            gdrive_df.to_csv(gdrive_csv_path, index=False)
            print(f"Extracted {len(gdrive_df)} Google Drive links to {gdrive_csv_path}")
            print(f"You can find the links at: {os.path.abspath(gdrive_csv_path)}")
        else:
            print("No Google Drive links found in the CSV")
        
        return gdrive_csv_path
    except Exception as e:
        print(f"Error extracting Google Drive links: {e}")
        return None

def extract_year_specific_links(csv_path, years_to_extract):
    """
    Extract links only from specific years and save to a separate CSV file.
    
    Args:
        csv_path: Path to the CSV file containing all links
        years_to_extract: List of years to extract (e.g., ["2024", "2025"])
    """
    try:
        output_folder = os.path.dirname(csv_path)
        years_str = "_".join(years_to_extract)
        output_filename = f"apbd_links_{years_str}.csv"
        output_path = os.path.join(output_folder, output_filename)
        
        # Read the original CSV
        df = pd.read_csv(csv_path)
        
        # Filter for specified years
        # Convert year column to string for safe comparison
        df['year'] = df['year'].astype(str)
        filtered_df = df[df['year'].isin(years_to_extract)]
        
        # Save to new CSV
        if not filtered_df.empty:
            filtered_df.to_csv(output_path, index=False)
            print(f"\n--- DOKUMEN APBD TAHUN {', '.join(years_to_extract)} ---")
            print(f"Jumlah dokumen: {len(filtered_df)}")
            print(f"File CSV tersimpan di: {os.path.abspath(output_path)}")
            
            # Print the documents for each year
            for year in years_to_extract:
                year_df = filtered_df[filtered_df['year'] == year]
                if not year_df.empty:
                    print(f"\nDokumen tahun {year} ({len(year_df)} dokumen):")
                    for i, row in year_df.iterrows():
                        print(f"- {row['document_title']}")
        else:
            print(f"Tidak ada dokumen untuk tahun {', '.join(years_to_extract)}")
        
        return output_path
    except Exception as e:
        print(f"Error extracting links for years {years_to_extract}: {e}")
        return None


if __name__ == "__main__":
    # Fix for SSL certificate issues on macOS
    import platform
    if platform.system() == 'Darwin':  # macOS
        import ssl
        # Use the macOS trusted certificates
        ssl._create_default_https_context = ssl._create_unverified_context
        print("Applied macOS SSL certificate fix")
    
    # Set to True to force a fresh scrape
    force_rescrape = True
    
    csv_path = "output/Pamekasan Regency/APBD/apbd_links.csv"
    if os.path.exists(csv_path) and not force_rescrape:
        print(f"Using existing CSV file: {csv_path}")
        extract_year_specific_links(csv_path, ["2024", "2025"])
        extract_google_drive_links(csv_path)
    else:
        # Run a fresh scrape
        print("Starting fresh scrape...")
        # Delete existing CSV file if force_rescrape is True
        if force_rescrape and os.path.exists(csv_path):
            os.remove(csv_path)
            print(f"Removed existing CSV file: {csv_path}")
            
        # Run the scraper with improved tab handling
        scraper = PamekasanAPBDScraper()
        documents = scraper.scrape()
        scraper.close()
        
        if documents:
            # Extract all Google Drive links
            extract_google_drive_links(scraper.csv_path)
            
            # Show documents for 2024 and 2025
            extract_year_specific_links(scraper.csv_path, ["2024", "2025"])
            
            # Show summary of all years
            print("\n--- RINGKASAN SEMUA DOKUMEN ---")
            df = pd.read_csv(scraper.csv_path)
            years = df['year'].astype(str).unique()
            for year in sorted(years):
                year_count = len(df[df['year'].astype(str) == year])
                print(f"Tahun {year}: {year_count} dokumen")
        else:
            print("Tidak ada dokumen yang ditemukan dalam proses scraping.")