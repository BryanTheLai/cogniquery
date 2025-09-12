# NEW FILE: src/cogniquery/mcps/web_search.py
import os
import json
import requests
from bs4 import BeautifulSoup

from .base import (
    WebSearchInput, WebSearchOutput, SearchResult,
    ScrapeWebsiteInput, ScrapeWebsiteOutput
)

def search_the_web(input_data: WebSearchInput) -> WebSearchOutput:
    """
    Performs a Google search using the Serper.dev API and returns structured results.
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return WebSearchOutput(success=False, error_message="SERPER_API_KEY is not set.")

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": input_data.query})
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        search_data = response.json()

        results = [
            SearchResult(
                title=item.get("title", "No Title"),
                link=item.get("link", "#"),
                snippet=item.get("snippet", "No Snippet")
            )
            for item in search_data.get("organic", [])
        ]
        
        return WebSearchOutput(success=True, results=results)

    except requests.exceptions.RequestException as e:
        return WebSearchOutput(success=False, error_message=f"HTTP Request failed: {e}")
    except Exception as e:
        return WebSearchOutput(success=False, error_message=f"An unexpected error occurred: {e}")


def scrape_website(input_data: ScrapeWebsiteInput) -> ScrapeWebsiteOutput:
    """
    Scrapes the text content of a given URL and returns a cleaned version.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(input_data.url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_content = '\n'.join(chunk for chunk in chunks if chunk)

        return ScrapeWebsiteOutput(success=True, clean_content=clean_content)

    except requests.exceptions.RequestException as e:
        return ScrapeWebsiteOutput(success=False, error_message=f"Failed to fetch or scrape URL: {e}")
    except Exception as e:
        return ScrapeWebsiteOutput(success=False, error_message=f"An unexpected error occurred during scraping: {e}")