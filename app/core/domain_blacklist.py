# Domain Blacklist Configuration
# This module contains the list of domains that should be banned from scraping and search results

from typing import List, Set
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

# Blacklisted domains - domains that should be skipped during scraping and search
BLACKLISTED_DOMAINS: Set[str] = {
    # Social Media Platforms
    "quora.com",
    "reddit.com",
    "tumblr.com",
    "wattpad.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "snapchat.com",
    "pinterest.com",
    "discord.com",
    "ask.fm",
    "researchgate.net",

    
    # Forums and Discussion Boards
    "4chan.org",
    "8chan.org",
    "somethingawful.com",
    "stackexchange.com",
    "stackoverflow.com",
    
    # Blog Platforms (Generic)
    "medium.com",
    "wordpress.com",
    "blogger.com",
    "blogspot.com",
    
    # Wiki and Reference Sites (Low Quality)
    "fandom.com",
    "tvtropes.org",
    "wikia.com",
    
    # Content Aggregators and Clickbait
    "buzzfeed.com",
    "ranker.com",
    "upworthy.com",
    "boredpanda.com",
    
    # Map and Geographic Services
    "openstreetmap.org",
    
    # Article Mills and Low-Quality Content
    "ezinearticles.com",
    "hubpages.com",
    "infobarrel.com",
    "ehow.com",
    "thoughtco.com",
    
    # Art and Entertainment
    "deviantart.com",
    "boardgamegeek.com",
    "myanimelist.net",
    "goodreads.com",
    
    # Torrent and Piracy Sites
    "thepiratebay.org",
    "limetorrents.info",
    
    # Deprecated/Old Web Services
    "geocities.com",
    "angelfire.com",
    
    # Conspiracy and Misinformation Sites
    "naturalnews.com",
    "infowars.com",
    "beforeitsnews.com",
    
    # Code Repositories (Not suitable for content scraping)
    "github.com",
}

def is_domain_blacklisted(url: str) -> bool:
    """
    Check if a URL's domain is blacklisted.
    
    Args:
        url (str): The URL to check
        
    Returns:
        bool: True if the domain is blacklisted, False otherwise
    """
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Check if domain is in blacklist
        is_blacklisted = domain in BLACKLISTED_DOMAINS
        
        if is_blacklisted:
            logger.info(f"🚫 Domain blacklisted: {domain}")
        
        return is_blacklisted
        
    except Exception as e:
        logger.error(f"Error checking domain blacklist for URL {url}: {str(e)}")
        return False

def filter_blacklisted_urls(urls: List[str]) -> List[str]:
    """
    Filter out blacklisted URLs from a list.
    
    Args:
        urls (List[str]): List of URLs to filter
        
    Returns:
        List[str]: List of URLs with blacklisted domains removed
    """
    filtered_urls = []
    blacklisted_count = 0
    
    for url in urls:
        if not is_domain_blacklisted(url):
            filtered_urls.append(url)
        else:
            blacklisted_count += 1
    
    if blacklisted_count > 0:
        logger.info(f"🚫 Filtered out {blacklisted_count} blacklisted URLs, kept {len(filtered_urls)} URLs")
    
    return filtered_urls

def filter_search_results(search_results: List) -> List:
    """
    Filter search results to remove blacklisted domains.
    Works with different search result formats.
    
    Args:
        search_results (List): List of search result objects
        
    Returns:
        List: Filtered search results
    """
    filtered_results = []
    blacklisted_count = 0
    
    for result in search_results:
        # Handle different search result formats
        url = None
        
        # Check different possible URL attributes
        if hasattr(result, 'url'):
            url = result.url
        elif hasattr(result, 'link'):
            url = result.link
        elif isinstance(result, dict):
            url = result.get('url') or result.get('link')
        
        if url and not is_domain_blacklisted(url):
            filtered_results.append(result)
        else:
            blacklisted_count += 1
            if url:
                logger.debug(f"🚫 Filtered out blacklisted result: {url}")
    
    if blacklisted_count > 0:
        logger.info(f"🚫 Filtered out {blacklisted_count} blacklisted search results, kept {len(filtered_results)} results")
    
    return filtered_results

def get_blacklisted_domains() -> Set[str]:
    """
    Get the set of blacklisted domains.
    
    Returns:
        Set[str]: Set of blacklisted domains
    """
    return BLACKLISTED_DOMAINS.copy()

def add_domain_to_blacklist(domain: str) -> None:
    """
    Add a domain to the blacklist.
    
    Args:
        domain (str): Domain to add to blacklist
    """
    domain = domain.lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    
    BLACKLISTED_DOMAINS.add(domain)
    logger.info(f"✅ Added domain to blacklist: {domain}")

def remove_domain_from_blacklist(domain: str) -> bool:
    """
    Remove a domain from the blacklist.
    
    Args:
        domain (str): Domain to remove from blacklist
        
    Returns:
        bool: True if domain was removed, False if it wasn't in the blacklist
    """
    domain = domain.lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    
    if domain in BLACKLISTED_DOMAINS:
        BLACKLISTED_DOMAINS.remove(domain)
        logger.info(f"✅ Removed domain from blacklist: {domain}")
        return True
    else:
        logger.warning(f"⚠️ Domain not found in blacklist: {domain}")
        return False 