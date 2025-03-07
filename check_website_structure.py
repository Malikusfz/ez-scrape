import requests
import os
from bs4 import BeautifulSoup
import warnings

# Suppress warnings about insecure requests
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

def inspect_page():
    url = "https://pamekasankab.go.id/berita/1"
    print(f"Checking structure of: {url}")
    
    try:
        # Disable SSL verification with verify=False
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, verify=False)
        
        if response.status_code == 200:
            print("Successfully fetched the page")
            
            # Save HTML to file for inspection
            with open("page_content.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("Saved HTML content to page_content.html")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different potential CSS selectors for article links
            potential_selectors = [
                "div.article-caption > a",
                "a.article-title",
                ".article-item a",
                ".news-item a",
                ".article a",
                ".post a",
                "article a",
                "h2 a",
                "h3 a",
                ".berita-item a",
                ".title a"
            ]
            
            print("\nChecking potential CSS selectors:")
            for selector in potential_selectors:
                elements = soup.select(selector)
                print(f"{selector}: Found {len(elements)} elements")
                
                # Print first few links if found
                if elements:
                    print("  First few links:")
                    for i, element in enumerate(elements[:3]):
                        print(f"  {i+1}. {element.get('href', 'No href')} - {element.get_text().strip()[:50]}")
            
            # Find all links on the page
            all_links = soup.find_all("a")
            print(f"\nTotal links on page: {len(all_links)}")
            
            # Check for news-related links
            news_links = [a for a in all_links if a.get('href') and '/berita/' in a.get('href')]
            print(f"Links with '/berita/' in href: {len(news_links)}")
            
            # Print first few news links
            if news_links:
                print("First 5 news links:")
                for i, link in enumerate(news_links[:5]):
                    print(f"{i+1}. {link.get('href')} - {link.get_text().strip()[:50]}")
            
    except Exception as e:
        print(f"Error inspecting page: {e}")

if __name__ == "__main__":
    inspect_page()