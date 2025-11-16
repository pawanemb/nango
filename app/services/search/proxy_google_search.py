#!/usr/bin/env python3
"""
Proxy Google Search

A robust script for performing Google searches through a proxy server.
Uses direct HTTP requests and BeautifulSoup for parsing results.
"""

import os
import sys
import time
import random
import argparse
import urllib3
from typing import List, Dict, Any, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse
from app.core.config import settings
# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default proxy configuration
DEFAULT_PROXY = settings.OXYLABS_PROXY_URL

# Country code to domain mapping
COUNTRY_DOMAINS = {
    "us": "com",      # United States
    "uk": "co.uk",    # United Kingdom
    "ca": "ca",       # Canada
    "au": "com.au",   # Australia
    "in": "co.in",    # India
    "de": "de",       # Germany
    "fr": "fr",       # France
    "jp": "co.jp",    # Japan
    "br": "com.br",   # Brazil
    "it": "it",       # Italy
    "ru": "ru",       # Russia
    "es": "es",       # Spain
    "mx": "com.mx",   # Mexico
    "za": "co.za",    # South Africa
    "ar": "com.ar",   # Argentina
    "ch": "ch",       # Switzerland
    "nl": "nl",       # Netherlands
    "se": "se",       # Sweden
    "pl": "pl",       # Poland
    "be": "be",       # Belgium
    "dk": "dk",       # Denmark
    "fi": "fi",       # Finland
    "no": "no",       # Norway
    "nz": "co.nz",    # New Zealand
    "ie": "ie",       # Ireland
    "sg": "com.sg",   # Singapore
    "hk": "com.hk",   # Hong Kong
    "tr": "com.tr",   # Turkey
    "ae": "ae",       # United Arab Emirates
    "th": "co.th",    # Thailand
}

class GoogleSearchResult:
    """Class to represent a Google search result"""
    
    def __init__(self, title: str, url: str, description: str = ""):
        self.title = title
        self.url = url
        self.description = description
    
    def __str__(self) -> str:
        return f"{self.title}\n{self.url}\n{self.description}"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "description": self.description
        }

def get_random_user_agent() -> str:
    """Return a random user agent string to avoid detection."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36 Edg/91.0.864.71"
    ]
    return random.choice(user_agents)

def extract_results_from_html(html_content: str) -> List[GoogleSearchResult]:
    """
    Extract search results from Google HTML content.
    
    Args:
        html_content: HTML content from Google search results page
        
    Returns:
        List of GoogleSearchResult objects
    """
    results = []
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Try different selectors to find search results
    # This is necessary because Google's HTML structure can change
    selectors = [
        "div.g", 
        "div.tF2Cxc", 
        "div.yuRUbf",
        "div[data-hveid]"
    ]
    
    found_results = False
    for selector in selectors:
        result_divs = soup.select(selector)
        if result_divs:
            found_results = True
            for div in result_divs:
                # Try to extract the link
                link_element = div.select_one("a")
                if not link_element:
                    continue
                
                url = link_element.get("href")
                
                # Skip non-http links and Google's own links
                if not url or not url.startswith("http"):
                    continue
                
                # Skip Google's own links
                parsed_url = urlparse(url)
                if "google" in parsed_url.netloc:
                    continue
                
                # Extract title
                title_element = div.select_one("h3")
                
                # Use URL domain as fallback title if no title is found
                if title_element and title_element.text.strip():
                    title = title_element.text.strip()
                else:
                    # Extract domain from URL as fallback title
                    domain = urlparse(url).netloc
                    title = domain.replace("www.", "")
                
                # Extract description
                desc_selectors = ["div.VwiC3b", "span.aCOpRe", "div.IsZvec"]
                description = ""
                
                for desc_selector in desc_selectors:
                    desc_element = div.select_one(desc_selector)
                    if desc_element:
                        description = desc_element.text.strip()
                        break
                
                # Create result object
                result = GoogleSearchResult(title, url, description)
                results.append(result)
            
            # If we found results with this selector, no need to try others
            break
    
    # If no results found with standard selectors, try to extract any links
    if not found_results:
        print("Could not identify result divs, attempting to extract links directly")
        links = soup.select("a[href^='http']")
        
        for link in links:
            href = link.get("href")
            if href.startswith("http"):
                # Skip Google's own links
                parsed_url = urlparse(href)
                if "google" in parsed_url.netloc:
                    continue
                
                # Use link text as title, or domain name if no text
                if link.text.strip():
                    title = link.text.strip()
                else:
                    domain = urlparse(href).netloc
                    title = domain.replace("www.", "")
                
                result = GoogleSearchResult(title, href)
                results.append(result)
    
    return results

def perform_google_search(
    query: str, 
    num_results: int = 10, 
    lang: str = "en",
    country: str = None,
    proxy: Optional[str] = None,
    timeout: int = 30,
    retry_count: int = 3
) -> List[GoogleSearchResult]:
    """
    Perform a Google search and return results.
    
    Args:
        query: Search query
        num_results: Number of results to return
        lang: Language for search results
        country: Country code for localized search (e.g., 'us', 'uk', 'in')
        proxy: Proxy URL to use
        timeout: Request timeout in seconds
        retry_count: Number of retries if the request fails
        
    Returns:
        List of GoogleSearchResult objects
    """
    # Configure session
    session = requests.Session()
    
    # Set user agent
    user_agent = get_random_user_agent()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": f"{lang},en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    })
    
    # Configure proxy if provided
    if proxy:
        session.proxies = {
            "http": proxy,
            "https": proxy
        }
        print(f"Using proxy: {proxy}")
    
    # Disable SSL verification
    session.verify = False
    
    # Determine Google domain based on country
    domain = "com"  # Default domain
    if country and country.lower() in COUNTRY_DOMAINS:
        domain = COUNTRY_DOMAINS[country.lower()]
        print(f"Using Google domain for {country}: google.{domain}")
    
    # Construct search URL
    encoded_query = quote_plus(query)
    url = f"https://www.google.{domain}/search?q={encoded_query}&hl={lang}&num={min(num_results, 100)}"
    
    # Add country parameter if specified
    if country:
        url += f"&gl={country.lower()}"
    
    print(f"Searching for: '{query}'")
    print(f"Search URL: {url}")
    
    results = []
    attempts = 0
    
    while attempts < retry_count and not results:
        try:
            # Send request
            response = session.get(url, timeout=timeout)
            
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code}")
                attempts += 1
                continue
            
            # Extract results from HTML
            results = extract_results_from_html(response.text)
            
            # Print results as they're found
            for result in results:
                print(f"Found: {result.url}")
            
            # Limit results to requested number
            results = results[:num_results]
            
        except Exception as e:
            print(f"Error during search (attempt {attempts+1}/{retry_count}): {str(e)}")
            attempts += 1
            
            if attempts < retry_count:
                # Wait before retrying
                wait_time = 2 ** attempts  # Exponential backoff
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
    
    return results

def save_results(results: List[GoogleSearchResult], filename: str) -> bool:
    """Save search results to a file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for i, result in enumerate(results, 1):
                f.write(f"Result {i}:\n")
                f.write(f"Title: {result.title}\n")
                f.write(f"URL: {result.url}\n")
                f.write(f"Description: {result.description}\n")
                f.write("-" * 80 + "\n")
        return True
    except Exception as e:
        print(f"Error saving results: {e}")
        return False

def save_results_as_json(results: List[GoogleSearchResult], filename: str) -> bool:
    """Save search results to a JSON file."""
    try:
        import json
        with open(filename, 'w', encoding='utf-8') as f:
            json_data = [result.to_dict() for result in results]
            json.dump(json_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving results as JSON: {e}")
        return False

def list_available_countries() -> None:
    """Print a list of available country codes and their Google domains."""
    print("Available country codes:")
    print("=" * 50)
    print(f"{'Code':<6} {'Domain':<15} {'Country'}")
    print("-" * 50)
    
    # Country name mapping for better display
    country_names = {
        "us": "United States",
        "uk": "United Kingdom",
        "ca": "Canada",
        "au": "Australia",
        "in": "India",
        "de": "Germany",
        "fr": "France",
        "jp": "Japan",
        "br": "Brazil",
        "it": "Italy",
        "ru": "Russia",
        "es": "Spain",
        "mx": "Mexico",
        "za": "South Africa",
        "ar": "Argentina",
        "ch": "Switzerland",
        "nl": "Netherlands",
        "se": "Sweden",
        "pl": "Poland",
        "be": "Belgium",
        "dk": "Denmark",
        "fi": "Finland",
        "no": "Norway",
        "nz": "New Zealand",
        "ie": "Ireland",
        "sg": "Singapore",
        "hk": "Hong Kong",
        "tr": "Turkey",
        "ae": "United Arab Emirates",
        "th": "Thailand",
    }
    
    for code, domain in sorted(COUNTRY_DOMAINS.items()):
        country = country_names.get(code, "")
        print(f"{code:<6} {'google.' + domain:<15} {country}")

def main():
    """Main function to parse arguments and execute search."""
    parser = argparse.ArgumentParser(description="Google Search with Proxy Support")
    parser.add_argument("query", nargs="*", help="Search query")
    parser.add_argument("--num", "-n", type=int, default=10, help="Number of results (default: 10)")
    parser.add_argument("--lang", "-l", default="en", help="Language (default: en)")
    parser.add_argument("--country", "-c", help="Country code for localized search (e.g., 'us', 'uk', 'in')")
    parser.add_argument("--proxy", "-p", default=DEFAULT_PROXY, help="Proxy URL")
    parser.add_argument("--no-proxy", action="store_true", help="Disable proxy usage")
    parser.add_argument("--output", "-o", help="Save results to file")
    parser.add_argument("--json", "-j", help="Save results to JSON file")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Request timeout in seconds (default: 30)")
    parser.add_argument("--retries", "-r", type=int, default=3, help="Number of retries if request fails (default: 3)")
    parser.add_argument("--list-countries", action="store_true", help="List available country codes")
    
    args = parser.parse_args()
    
    # Show country list if requested
    if args.list_countries:
        list_available_countries()
        return
    
    # Handle case when query is provided as separate arguments
    query = " ".join(args.query) if args.query else input("Enter search query: ")
    
    # Determine if proxy should be used
    proxy = None if args.no_proxy else args.proxy
    
    # Perform the search
    start_time = time.time()
    results = perform_google_search(
        query, 
        args.num, 
        args.lang,
        args.country,
        proxy,
        args.timeout,
        args.retries
    )
    end_time = time.time()
    
    # Display results
    if results:
        print(f"\nSearch Results for '{query}':")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.title}")
            print(f"   {result.url}")
            description_preview = result.description[:100] + "..." if len(result.description) > 100 else result.description
            print(f"   {description_preview}")
            print()
        
        print(f"Found {len(results)} results in {end_time - start_time:.2f} seconds.")
        
        # Save results if output file is specified
        if args.output:
            if save_results(results, args.output):
                print(f"Results saved to {args.output}")
            else:
                print(f"Failed to save results to {args.output}")
        
        # Save results as JSON if specified
        if args.json:
            if save_results_as_json(results, args.json):
                print(f"Results saved as JSON to {args.json}")
            else:
                print(f"Failed to save results as JSON to {args.json}")
    else:
        print("No results found or an error occurred.")

if __name__ == "__main__":
    main()
