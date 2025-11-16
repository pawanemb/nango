from typing import List, Dict, Optional
import os
import requests
from dataclasses import dataclass
from urllib.parse import quote
import logging

@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str
    date_published: Optional[str] = None

def google_custom_search(
    query: str,
    api_key: Optional[str] = None,
    search_engine_id: Optional[str] = None
) -> List[SearchResult]:
    """
    Perform a Google Custom Search and return formatted results.
    
    Args:
        query (str): The search query
        api_key (str, optional): Google API key. If not provided, will look for GOOGLE_API_KEY env variable
        search_engine_id (str, optional): Custom Search Engine ID. If not provided, will look for GOOGLE_CSE_ID env variable
    
    Returns:
        List[SearchResult]: List of search results with title, link, snippet, and publication date
    """
    # Get API credentials
    api_key = api_key or os.getenv('GOOGLE_API_KEY')
    search_engine_id = search_engine_id or os.getenv('GOOGLE_CSE_ID')
    
    if not api_key or not search_engine_id:
        raise ValueError(
            "Google API key and Search Engine ID are required. "
            "Either pass them as parameters or set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables."
        )
    
    try:
        endpoint = (
            f"https://www.googleapis.com/customsearch/v1"
            f"?key={api_key}&cx={search_engine_id}"
            f"&q={quote(query)}"
        )
        
        logging.info(f"Making request to Google Custom Search API")
        response = requests.get(endpoint)
        
        if response.status_code != 200:
            logging.error(f"API request failed with status code: {response.status_code}")
            logging.error(f"Error message: {response.text}")
            return []

        data = response.json()

        # Check if we have search results
        if 'items' not in data:
            logging.info("No search results found")
            return []

        results = []
        for item in data['items']:
            # Extract publication date from metatags if available
            date_published = None
            if 'pagemap' in item and 'metatags' in item['pagemap']:
                metatags = item['pagemap']['metatags'][0]
                # Try different possible date fields
                date_fields = [
                    'article:published_time',
                    'datePublished',
                    'og:updated_time',
                    'article:modified_time'
                ]
                for field in date_fields:
                    if field in metatags:
                        date_published = metatags[field]
                        break

            # Create SearchResult object with all available fields
            result = SearchResult(
                title=item.get('title', ''),
                link=item.get('link', ''),
                snippet=item.get('snippet', ''),
                date_published=date_published
            )
            results.append(result)

            # Log the extracted data for debugging
            logging.debug(f"Processed search result: {vars(result)}")

        return results

    except Exception as e:
        logging.error(f"Error during Google search: {str(e)}")
        return []

# Example usage
if __name__ == "__main__":
    # Example search
    results = google_custom_search("Computer Science Introduction")
    
    # Print results
    for result in results:
        print(f"\nTitle: {result.title}")
        print(f"Link: {result.link}")
        print(f"Snippet: {result.snippet}")
        if result.date_published:
            print(f"Published: {result.date_published}")
        print("-" * 50)
