import os
import csv
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


def setup_webdriver(output_folder):
    """
    Set up the WebDriver with the specified download directory.
    """
    output_folder = os.path.abspath(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": output_folder,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "printing.default_destination_selection_rules": {
            "kind": "pdf",
            "namePattern": "Save as PDF"
        },
        "printing.print_preview_sticky_settings.appState": {
            "recentDestinations": [{
                "id": "Save as PDF",
                "origin": "local",
                "account": ""
            }],
            "selectedDestinationId": "Save as PDF",
            "version": 2,
            "isHeaderFooterEnabled": False,
            "isLandscapeEnabled": False,
            "marginsType": 0,
            "scaling": 100,
            "scalingType": 3,
            "isCssBackgroundEnabled": True,
            "mediaSize": {"height_microns": 297000, "width_microns": 210000}
        }
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--kiosk-printing")
    options.add_argument("--disable-print-preview")

    return webdriver.Chrome(options=options)


def wait_for_download(path, max_wait_time=300):
    """
    Wait for all downloads to complete in the specified directory.
    """
    start_time = time.time()
    while True:
        downloading = any(file.endswith(".crdownload") for file in os.listdir(path))
        if not downloading:
            break
        if time.time() - start_time > max_wait_time:
            logging.warning("Download timeout occurred.")
            break
        time.sleep(2)


def scrape_from_list(link_list, output_folder, update_progress=None):
    """
    Visit each link in the list and trigger downloads.
    """
    driver = setup_webdriver(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    total_links = len(link_list)
    for idx, link in enumerate(link_list):
        try:
            # Check if PDF already exists
            expected_filename = os.path.join(output_folder, f"document_{idx + 1}.pdf")
            if os.path.exists(expected_filename):
                logging.info(f"PDF already exists for {link}, skipping...")
                if update_progress:
                    update_progress(idx + 1, total_links, f"Skipped existing PDF {idx + 1}/{total_links}")
                continue

            driver.get(link)
            logging.info(f"{idx + 1}/{total_links} - Downloading PDF from {link}")
            initial_files = set(os.listdir(output_folder))

            # Look for direct download links first
            download_selectors = [
                "a[href$='.pdf']",
                "a[href*='pdf']",
                "a[download]",
                "a[href*='download']"
            ]

            # Try direct download links first
            pdf_downloaded = False
            for selector in download_selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    if elements:
                        elements[0].click()
                        time.sleep(2)
                        pdf_downloaded = True
                        break
                except Exception as e:
                    continue

            # If no direct download link found, try print dialog approach
            if not pdf_downloaded:
                # Try to trigger print dialog with keyboard shortcut first
                actions = ActionChains(driver)
                actions.key_down(Keys.COMMAND).send_keys('p').key_up(Keys.COMMAND).perform()
                time.sleep(2)

                # Press Enter to confirm print dialog and wait longer
                actions.send_keys(Keys.RETURN).perform()
                time.sleep(5)  # Increased wait time for dialog processing

                # Only try print selectors if keyboard shortcut didn't work
                if not any(f.endswith('.pdf') or f.endswith('.crdownload') for f in os.listdir(output_folder)):
                    print_selectors = [
                        ".download.av a[onclick*='print']",
                        "a[onclick*='print']",
                        ".fa-print",
                        ".fa-file-pdf-o",
                        "[onclick*='print']"
                    ]

                    for selector in print_selectors:
                        try:
                            elements = driver.find_elements("css selector", selector)
                            if elements:
                                elements[0].click()
                                time.sleep(3)  # Increased wait time
                                actions.send_keys(Keys.RETURN).perform()
                                time.sleep(3)  # Wait after confirming dialog
                                break
                        except Exception as e:
                            continue

            # Wait for new file to appear
            max_wait = 30
            start_wait = time.time()
            new_file_found = False

            while time.time() - start_wait < max_wait:
                current_files = set(os.listdir(output_folder))
                new_files = current_files - initial_files
                if new_files:
                    # Move and rename the new file
                    for new_file in new_files:
                        if new_file.endswith('.pdf') or new_file.endswith('.crdownload'):
                            source_path = os.path.join(output_folder, new_file)
                            if os.path.exists(expected_filename):
                                os.remove(expected_filename)
                            if new_file.endswith('.crdownload'):
                                wait_for_download(output_folder)
                            if os.path.exists(source_path):
                                os.rename(source_path, expected_filename)
                            new_file_found = True
                            break
                if new_file_found:
                    break
                time.sleep(1)

            # Update progress
            if update_progress:
                update_progress(idx + 1, total_links, f"Downloading {idx + 1}/{total_links} PDFs...")
        except Exception as e:
            logging.error(f"Failed to download PDF from {link}: {e}")

    wait_for_download(output_folder)
    driver.quit()

def pdf_scraper_main(csv_path, project_folder, update_progress=None, log_callback=None):
    """
    Main function to scrape PDFs from links in a CSV file.
    """
    # Configure log file
    logs_folder = os.path.join(project_folder, "pdfs", "logs")
    os.makedirs(logs_folder, exist_ok=True)
    log_file = os.path.join(logs_folder, "pdf_scraper.log")

    # Explicitly configure logging
    logger = logging.getLogger("PDFScraper")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

    # Log startup message
    logger.info("PDF Scraper started.")

    # Configure output folder for PDFs
    pdf_output_folder = os.path.join(project_folder, "pdfs", "scraped-pdfs")
    os.makedirs(pdf_output_folder, exist_ok=True)

    # Read links from the CSV file
    try:
        with open(csv_path, "r") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header row
            link_list = [row[0] for row in reader]
    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        raise

    # Log total links
    logger.info(f"Total links to process: {len(link_list)}")

    # Scrape PDFs
    try:
        scrape_from_list(link_list=link_list, output_folder=pdf_output_folder, update_progress=update_progress)
    except Exception as e:
        logger.error(f"Error during PDF scraping: {e}")
        raise

    # Log completion message
    logger.info("PDF Scraper completed.")
    if log_callback:
        log_callback("PDF download completed.")


