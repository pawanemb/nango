"""
🚀 Fast Async Scraper Service using aiohttp + Oxylabs proxy
Optimized for high-performance web scraping with async/await
"""

import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import re
from datetime import datetime
from app.core.config import settings
from app.core.logging_config import logger
from app.core.domain_blacklist import is_domain_blacklisted

# Serper API handles country localization automatically through 'gl' parameter


class FastAsyncScraper:
    """Fast async web scraper using aiohttp + Oxylabs proxy"""
    
    def __init__(self):
        self.proxy_auth = aiohttp.BasicAuth(settings.OXYLABS_USERNAME, settings.OXYLABS_PASSWORD)
        self.proxy_url = 'http://unblock.oxylabs.io:60000'
        
        
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',  # Removed 'br' (brotli) to avoid decoding issues
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
    
    async def scrape_url(self, url: str, timeout: int = 12) -> str:
        """
        Fast async URL scraping with Oxylabs proxy
        
        Args:
            url: URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            str: Extracted clean text content
            
        Raises:
            Exception: If scraping fails
        """
        scrape_start_time = datetime.now()
        logger.info(f"🔍 [WEBSITE-SCRAPE] Starting website scraping for URL: {url}")
        logger.info(f"🔧 [WEBSITE-SCRAPE] Using proxy: {self.proxy_url}")
        logger.info(f"⏱️ [WEBSITE-SCRAPE] Timeout set to: {timeout} seconds")
        logger.info(f"🕒 [WEBSITE-SCRAPE] Started at: {scrape_start_time.strftime('%H:%M:%S.%f')[:-3]}")
        
        
        try:
            # Create connector with optimized settings
            connector = aiohttp.TCPConnector(
                ssl=False,  # Ignore SSL as per Oxylabs docs
                limit=100,  # Connection pool size
                limit_per_host=10,  # Max connections per host
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True
            )
            logger.info(f"🌐 [WEBSITE-SCRAPE] TCP connector created with SSL disabled")
            logger.info(f"🔧 [WEBSITE-SCRAPE] Connector settings - Pool: 100, Per host: 10, DNS cache: 300s")
            
            async with aiohttp.ClientSession(connector=connector) as session:
                logger.info(f"📡 [WEBSITE-SCRAPE] Sending GET request to {url}")
                logger.info(f"📋 [WEBSITE-SCRAPE] Headers: {self.default_headers}")
                logger.info(f"🔐 [WEBSITE-SCRAPE] Using proxy auth: {self.proxy_url}")
                
                async with session.get(
                    url,
                    headers=self.default_headers,
                    proxy=self.proxy_url,
                    proxy_auth=self.proxy_auth,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    allow_redirects=True,  # Follow redirects automatically
                    max_redirects=10  # Allow up to 10 redirects
                ) as response:
                    response_time = (datetime.now() - scrape_start_time).total_seconds()
                    logger.info(f"📈 [WEBSITE-SCRAPE] Response received in {response_time:.3f}s - Status: {response.status}")
                    logger.info(f"🌍 [WEBSITE-SCRAPE] Final URL after redirects: {response.url}")
                    logger.info(f"📋 [WEBSITE-SCRAPE] Response headers: {dict(response.headers)}")
                    
                    if str(response.url) != url:
                        logger.info(f"↩️ [WEBSITE-SCRAPE] Redirected from {url} to {response.url}")
                        logger.info(f"🔄 [WEBSITE-SCRAPE] Redirect chain analysis needed")
                    
                    
                    # Check response status
                    if response.status == 403:
                        logger.error(f"🚫 [WEBSITE-SCRAPE] 403 Forbidden received from {url}")
                        logger.error(f"🔍 [WEBSITE-SCRAPE] Possible bot detection or IP blocking")
                        raise Exception(f"403 Forbidden: The website is blocking automated access")
                    elif response.status == 404:
                        logger.error(f"❌ [WEBSITE-SCRAPE] 404 Not Found received from {url}")
                        logger.error(f"🔍 [WEBSITE-SCRAPE] Page does not exist or URL is incorrect")
                        raise Exception(f"404 Not Found: The page does not exist")
                    elif response.status >= 400:
                        logger.error(f"⚠️ [WEBSITE-SCRAPE] HTTP {response.status} error received from {url}")
                        logger.error(f"🔍 [WEBSITE-SCRAPE] Server error or client request issue")
                        
                        # Log response content for debugging
                        try:
                            response_text = await response.text()
                            logger.error(f"🔍 [WEBSITE-SCRAPE] Error response content: {response_text[:500]}")
                            
                            # Check if this is an Oxylabs error
                            if "Provided `url` is not supported" in response_text:
                                logger.warning(f"⚠️ [WEBSITE-SCRAPE] Oxylabs blocked {url}")
                                raise Exception(f"Oxylabs proxy rejected URL: {url}")
                            elif "rate limit" in response_text.lower():
                                logger.error(f"🚫 [WEBSITE-SCRAPE] Rate limit exceeded for proxy service")
                                raise Exception(f"Rate limit exceeded for proxy service")
                            else:
                                logger.error(f"🔍 [WEBSITE-SCRAPE] Generic HTTP error: {response_text[:200]}")
                                raise Exception(f"HTTP {response.status}: {response_text[:200]}")
                        except Exception as read_error:
                            if "Oxylabs proxy rejected URL" in str(read_error) or "Rate limit exceeded" in str(read_error):
                                raise read_error
                            logger.error(f"🔍 [WEBSITE-SCRAPE] Could not read error response content: {str(read_error)}")
                            raise Exception(f"HTTP {response.status}: Website blocked request - {url}")
                    
                    logger.info(f"✅ [WEBSITE-SCRAPE] Successful response received, reading content...")
                    html_content = await response.text()
                    content_read_time = (datetime.now() - scrape_start_time).total_seconds()
                    logger.info(f"📄 [WEBSITE-SCRAPE] Retrieved {len(html_content)} chars from {url} in {content_read_time:.3f}s")
                    
                    # Check if we got meaningful content
                    if len(html_content) < 100:
                        logger.error(f"📉 [WEBSITE-SCRAPE] Insufficient content: only {len(html_content)} chars from {url}")
                        logger.error(f"💾 [WEBSITE-SCRAPE] Content preview: {html_content[:200] if html_content else 'None'}")
                        logger.error(f"🔍 [WEBSITE-SCRAPE] Possible bot detection, captcha, or empty page")
                        raise Exception(f"Insufficient content retrieved: only {len(html_content)} characters")
                    
                    # Check for common anti-bot patterns
                    html_lower = html_content.lower()
                    if any(pattern in html_lower for pattern in ['captcha', 'cloudflare', 'access denied', 'blocked']):
                        logger.warning(f"🤖 [WEBSITE-SCRAPE] Possible bot detection patterns found in HTML")
                        logger.warning(f"🔍 [WEBSITE-SCRAPE] HTML sample: {html_content[:300]}")
                    
                    logger.info(f"🔄 [WEBSITE-SCRAPE] Starting content extraction for {url}")
                    # Extract clean text content
                    extracted_content = await self._extract_content_async(html_content, url)
                    total_time = (datetime.now() - scrape_start_time).total_seconds()
                    logger.info(f"✅ [WEBSITE-SCRAPE] Content extraction completed in {total_time:.3f}s. Final length: {len(extracted_content)} chars")
                    
                    # Quality check on extracted content
                    if len(extracted_content.strip()) < 50:
                        logger.warning(f"⚠️ [WEBSITE-SCRAPE] Very short extracted content: {len(extracted_content)} chars")
                        logger.warning(f"🔍 [WEBSITE-SCRAPE] Extracted preview: {extracted_content[:200]}")
                    
                    return extracted_content
                    
        except asyncio.TimeoutError as timeout_error:
            total_time = (datetime.now() - scrape_start_time).total_seconds()
            logger.error(f"⏰ [WEBSITE-SCRAPE] Timeout after {total_time:.3f}s for URL: {url}")
            logger.error(f"⏰ [WEBSITE-SCRAPE] Timeout details: {str(timeout_error)}")
            logger.error(f"⏰ [WEBSITE-SCRAPE] Configured timeout was: {timeout}s")
            raise Exception("Request timeout: The website took too long to respond")
        except aiohttp.ClientError as client_error:
            total_time = (datetime.now() - scrape_start_time).total_seconds()
            logger.error(f"🔌 [WEBSITE-SCRAPE] Client error after {total_time:.3f}s: {str(client_error)}")
            logger.error(f"🔌 [WEBSITE-SCRAPE] Client error type: {type(client_error).__name__}")
            logger.error(f"🔌 [WEBSITE-SCRAPE] URL: {url}")
            raise Exception(f"Connection error: {str(client_error)}")
        except Exception as e:
            total_time = (datetime.now() - scrape_start_time).total_seconds()
            logger.error(f"💥 [WEBSITE-SCRAPE] Unexpected error after {total_time:.3f}s: {type(e).__name__}")
            logger.error(f"💥 [WEBSITE-SCRAPE] Error details: {str(e)}")
            logger.error(f"💥 [WEBSITE-SCRAPE] URL: {url}")
            logger.error(f"💥 [WEBSITE-SCRAPE] Domain: {domain}")
            raise Exception(f"Failed to scrape: {str(e)}")
    
    async def scrape_multiple_urls(self, urls: List[str], timeout: int = 12, max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently with rate limiting
        
        Args:
            urls: List of URLs to scrape
            timeout: Request timeout per URL
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List[Dict]: Results with url, content, success status
        """
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    content = await self.scrape_url(url, timeout)
                    return {
                        "url": url,
                        "content": content,
                        "success": True,
                        "error": None,
                        "content_length": len(content)
                    }
                except Exception as e:
                    logger.error(f"❌ Failed to scrape {url}: {str(e)}")
                    return {
                        "url": url,
                        "content": "",
                        "success": False,
                        "error": str(e),
                        "content_length": 0
                    }
        
        # Execute all URLs concurrently
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        successful = sum(1 for r in results if r["success"])
        logger.info(f"✅ Scraped {successful}/{len(urls)} URLs successfully")
        
        return results
    
    async def google_search(self, query: str, max_results: int = 5, timeout: int = 15, country: str = "us") -> List[Dict[str, str]]:
        """
        Google search using Serper API for better reliability and performance
        
        Args:
            query: Search query
            max_results: Maximum results to return
            timeout: Request timeout
            country: Country code for localized search (e.g., 'us', 'uk', 'in')
            
        Returns:
            List[Dict]: Search results with title, link, snippet
        """
        search_start_time = datetime.now()
        logger.info(f"🔍 [SERPER-SEARCH] Starting Serper Google search for query: '{query}'")
        logger.info(f"🌍 [SERPER-SEARCH] Country: {country}, Max results: {max_results}, Timeout: {timeout}s")
        
        try:
            # Serper API endpoint
            serper_url = "https://google.serper.dev/search"
            
            # Prepare request parameters
            params = {
                'q': query,
                'gl': country.lower() if country else 'us',
                'apiKey': settings.SERPER_API_KEY
            }
            
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': settings.SERPER_API_KEY
            }
            
            logger.info(f"🔗 [SERPER-SEARCH] Serper API URL: {serper_url}")
            logger.info(f"🌐 [SERPER-SEARCH] Parameters: q='{query}', gl='{params['gl']}'")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    serper_url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response_time = (datetime.now() - search_start_time).total_seconds()
                    logger.info(f"📈 [SERPER-SEARCH] Response received in {response_time:.3f}s - Status: {response.status}")
                    
                    if response.status != 200:
                        logger.error(f"❌ [SERPER-SEARCH] Non-200 status: {response.status}")
                        error_content = await response.text()
                        logger.error(f"🔍 [SERPER-SEARCH] Error content: {error_content}")
                        raise Exception(f"Serper API returned status {response.status}")
                    
                    json_response = await response.json()
                    logger.info(f"📄 [SERPER-SEARCH] Retrieved JSON response: {len(str(json_response))} characters")
                    
                    # Parse Serper API response format
                    search_results = []
                    organic_results = json_response.get('organic', [])
                    
                    logger.info(f"🔄 [SERPER-SEARCH] Processing {len(organic_results)} organic results...")
                    
                    # Convert Serper format to our expected format
                    for i, result in enumerate(organic_results[:max_results]):
                        search_result = {
                            "title": result.get("title", ""),
                            "link": result.get("link", ""),
                            "snippet": result.get("snippet", "")
                        }
                        
                        # Filter out blacklisted domains
                        if is_domain_blacklisted(search_result["link"]):
                            logger.info(f"🚫 [SERPER-SEARCH] Skipping blacklisted domain: {search_result['link']}")
                            continue
                            
                        search_results.append(search_result)
                        
                        # Stop if we have enough results
                        if len(search_results) >= max_results:
                            break
                    
                    # Only return first 3 results for processing (same as original implementation)
                    results_to_process = search_results[:3]
                    
                    total_time = (datetime.now() - search_start_time).total_seconds()
                    logger.info(f"✅ [SERPER-SEARCH] Completed in {total_time:.3f}s - Found {len(results_to_process)} results")
                    
                    if not results_to_process:
                        logger.warning(f"⚠️ [SERPER-SEARCH] No search results found for query: '{query}'")
                        logger.warning(f"🔍 [SERPER-SEARCH] Response preview: {str(json_response)[:500]}")
                    else:
                        for i, result in enumerate(results_to_process):
                            logger.info(f"📋 [SERPER-SEARCH] Result {i+1}: {result.get('title', 'No title')[:50]}... -> {result.get('link', 'No link')}")
                    
                    return results_to_process
                    
        except asyncio.TimeoutError as timeout_error:
            total_time = (datetime.now() - search_start_time).total_seconds()
            logger.error(f"⏰ [SERPER-SEARCH] Timeout after {total_time:.3f}s for query: '{query}'")
            logger.error(f"⏰ [SERPER-SEARCH] Timeout details: {str(timeout_error)}")
            return []
        except aiohttp.ClientError as client_error:
            total_time = (datetime.now() - search_start_time).total_seconds()
            logger.error(f"🔌 [SERPER-SEARCH] Client error after {total_time:.3f}s: {str(client_error)}")
            logger.error(f"🔌 [SERPER-SEARCH] Query: '{query}', Country: {country}")
            return []
        except Exception as e:
            total_time = (datetime.now() - search_start_time).total_seconds()
            logger.error(f"💥 [SERPER-SEARCH] Unexpected error after {total_time:.3f}s: {type(e).__name__}")
            logger.error(f"💥 [SERPER-SEARCH] Error details: {str(e)}")
            logger.error(f"💥 [SERPER-SEARCH] Query: '{query}', Country: {country}")
            return []
    
    async def _extract_content_async(self, html_content: str, url: str) -> str:
        """Extract clean text content from HTML asynchronously"""
        
        def extract_content_sync(html_content: str) -> str:
            """Synchronous content extraction to run in thread pool"""
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove unwanted elements safely
                unwanted_tags = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']
                for tag in unwanted_tags:
                    for element in soup.find_all(tag):
                        element.decompose()
                
                # Try multiple content extraction strategies
                content_selectors = [
                    'article',
                    'main',
                    '.content',
                    '.post-content', 
                    '.entry-content',
                    '.article-content',
                    '#content',
                    'body'
                ]
                
                extracted_content = ""
                for selector in content_selectors:
                    try:
                        elements = soup.select(selector)
                        if elements:
                            extracted_content = elements[0].get_text()
                            if len(extracted_content.strip()) > 200:  # Good content threshold
                                break
                    except Exception as sel_error:
                        logger.warning(f"⚠️ [DEBUG] Selector '{selector}' failed: {str(sel_error)}")
                        continue
                
                # Fallback to full body text if no specific content area found
                if len(extracted_content.strip()) < 200:
                    extracted_content = soup.get_text()
                
                # Clean content
                content = re.sub(r'\s+', ' ', extracted_content).strip()
                
                # Check final content quality
                if len(content) < 100:
                    raise Exception(f"Failed to extract meaningful content: only {len(content)} characters extracted")
                
                return content[:6000]  # Limit content length
            
            except Exception as extract_error:
                logger.error(f"💥 [DEBUG] BeautifulSoup extraction error: {str(extract_error)}")
                # Return raw text as fallback
                import html
                try:
                    # Simple text extraction fallback
                    clean_text = re.sub(r'<[^>]+>', '', html_content)
                    clean_text = html.unescape(clean_text)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    return clean_text[:6000] if clean_text else "Failed to extract content"
                except Exception:
                    raise Exception("Complete content extraction failure")
        
        # Extract content synchronously (simplified)
        try:
            content = extract_content_sync(html_content)
            logger.info(f"✅ Successfully extracted {len(content)} chars from {url}")
            return content
        except Exception as e:
            logger.error(f"💥 [DEBUG] Content extraction failed: {str(e)}")
            raise Exception(f"Content extraction failed: {str(e)}")
    


    
    
    async def search_and_scrape_first_result(self, query: str, country: str = "us", user_id: str = None, project_id: str = None, blog_id: str = None) -> Dict[str, Any]:
        """
        Simple pipeline: Google search + scrape ONLY the first result
        
        Args:
            query: Search query
            country: Country code for localized search
            user_id: User ID for tracking
            project_id: Project ID for tracking
            blog_id: Blog ID for tracking
            
        Returns:
            Dict: Single result with search data and scraped content
        """
        pipeline_start_time = datetime.now()
        logger.info(f"🚀 [PIPELINE] Starting search_and_scrape_first_result pipeline")
        logger.info(f"🔍 [PIPELINE] Query: '{query}', Country: {country}")
        logger.info(f"🕒 [PIPELINE] Started at: {pipeline_start_time.strftime('%H:%M:%S.%f')[:-3]}")
        
        try:
            # Step 1: Google search (get just 1 result)
            logger.info(f"1️⃣ [PIPELINE] STEP 1: Starting Google search...")
            search_start = datetime.now()
            search_results = await self.google_search(query, max_results=1, country=country)
            search_duration = (datetime.now() - search_start).total_seconds()
            logger.info(f"1️⃣ [PIPELINE] STEP 1 completed in {search_duration:.3f}s")
            
            if not search_results:
                total_time = (datetime.now() - pipeline_start_time).total_seconds()
                logger.warning(f"❌ [PIPELINE] No Google results for: '{query}' (total time: {total_time:.3f}s)")
                logger.warning(f"🔍 [PIPELINE] Possible issues: Query too specific, regional blocking, or Google rate limiting")
                return {
                    "title": "No results found",
                    "url": f"search://no-results-for-{query}",
                    "snippet": f"No search results found for: {query}",
                    "content": "",
                    "success": False,
                    "error": "No search results",
                    "content_length": 0,
                    "source_query": query
                }
            
            # Step 2: Take only the FIRST result
            first_result = search_results[0]
            first_url = first_result["link"]
            
            logger.info(f"2️⃣ [PIPELINE] STEP 2: Selected first result")
            logger.info(f"🎯 [PIPELINE] Title: {first_result['title'][:100]}...")
            logger.info(f"🔗 [PIPELINE] URL: {first_url}")
            logger.info(f"📝 [PIPELINE] Snippet: {first_result['snippet'][:150]}...")
            
            # Step 3: Scrape only this one URL with RayoScraper
            logger.info(f"3️⃣ [PIPELINE] STEP 3: Starting website scraping with RayoScraper...")
            scrape_start = datetime.now()
            try:
                # Use RayoScraper with proper user/project tracking
                from app.services.rayo_scraper import RayoScrapingService
                rayo_scraper = RayoScrapingService(user_id=user_id or "search-pipeline")
                
                # Simple payload with only required fields + comments
                additional_metadata = {
                    "comments": "Sources collection scraping"
                }
                
                rayo_result = await rayo_scraper.scrape_website(
                    url=first_url,
                    project_id=project_id,
                    blog_id=blog_id,
                    additional_metadata=additional_metadata
                )
                
                if rayo_result.get("status") == "completed" and rayo_result.get("content"):
                    content = rayo_result["content"]
                else:
                    raise Exception(f"RayoScraper failed: {rayo_result.get('error', 'Unknown error')}")
                scrape_duration = (datetime.now() - scrape_start).total_seconds()
                logger.info(f"3️⃣ [PIPELINE] STEP 3 completed in {scrape_duration:.3f}s")
                
                total_time = (datetime.now() - pipeline_start_time).total_seconds()
                logger.info(f"✅ [PIPELINE] SUCCESS! Total pipeline time: {total_time:.3f}s")
                logger.info(f"📊 [PIPELINE] Content extracted: {len(content)} characters")
                
                return {
                    "title": first_result["title"],
                    "url": first_url,
                    "snippet": first_result["snippet"],
                    "content": content,
                    "success": True,
                    "error": None,
                    "content_length": len(content),
                    "source_query": query
                }
                
            except Exception as scrape_error:
                scrape_duration = (datetime.now() - scrape_start).total_seconds()
                total_time = (datetime.now() - pipeline_start_time).total_seconds()
                logger.error(f"❌ [PIPELINE] STEP 3 FAILED after {scrape_duration:.3f}s: {scrape_error}")
                logger.error(f"💥 [PIPELINE] Scraping error type: {type(scrape_error).__name__}")
                logger.error(f"🔗 [PIPELINE] Failed URL: {first_url}")
                logger.error(f"⏱️ [PIPELINE] Total pipeline time: {total_time:.3f}s")
                
                return {
                    "title": first_result["title"],
                    "url": first_url,
                    "snippet": first_result["snippet"],
                    "content": "",
                    "success": False,
                    "error": str(scrape_error),
                    "content_length": 0,
                    "source_query": query
                }
            
        except Exception as e:
            total_time = (datetime.now() - pipeline_start_time).total_seconds()
            logger.error(f"💥 [PIPELINE] COMPLETE FAILURE after {total_time:.3f}s for query: '{query}'")
            logger.error(f"💥 [PIPELINE] Error type: {type(e).__name__}")
            logger.error(f"💥 [PIPELINE] Error details: {str(e)}")
            logger.error(f"🌍 [PIPELINE] Country: {country}")
            
            return {
                "title": "Pipeline error",
                "url": f"error://pipeline-failed-{query}",
                "snippet": f"Pipeline failed for: {query}",
                "content": "",
                "success": False,
                "error": str(e),
                "content_length": 0,
                "source_query": query
            }

    async def scrape_and_search_pipeline(self, query: str, max_results: int = 3, country: str = "us") -> List[Dict[str, Any]]:
        """
        Complete pipeline: Google search + scrape all results
        
        Args:
            query: Search query
            max_results: Maximum results to process
            country: Country code for localized search (e.g., 'us', 'uk', 'in')
            
        Returns:
            List[Dict]: Complete results with search data and scraped content
        """
        try:
            # Step 1: Google search with country localization
            search_results = await self.google_search(query, max_results=max_results+2, country=country)  # Get extra, process requested
            
            if not search_results:
                logger.warning(f"❌ No Google results for: {query}")
                return []
            
            logger.info(f"✅ Google search complete: Found {len(search_results)} URLs - Starting scraping...")
            
            # Step 2: Scrape all URLs concurrently
            urls = [result["link"] for result in search_results]
            scrape_results = await self.scrape_multiple_urls(urls, timeout=20, max_concurrent=18)
            
            # Step 3: Combine search and scrape results
            combined_results = []
            for search_result, scrape_result in zip(search_results, scrape_results):
                combined_results.append({
                    "title": search_result["title"],
                    "url": search_result["link"],
                    "snippet": search_result["snippet"],
                    "content": scrape_result["content"] if scrape_result["success"] else "",
                    "success": scrape_result["success"],
                    "error": scrape_result.get("error"),
                    "content_length": len(scrape_result["content"]) if scrape_result["success"] else 0
                })
            
            successful_scrapes = sum(1 for r in combined_results if r["success"])
            logger.info(f"🎯 Pipeline complete: {successful_scrapes}/{len(search_results)} URLs successfully scraped")
            
            return combined_results
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed for '{query}': {str(e)}")
            return []


# Factory function for easy import
def create_fast_scraper() -> FastAsyncScraper:
    """Create a new FastAsyncScraper instance"""
    return FastAsyncScraper()


# Usage example
async def example_usage():
    """Example of how to use the FastAsyncScraper"""
    scraper = create_fast_scraper()
    
    # Single URL scraping
    content = await scraper.scrape_url("https://example.com")
    print(f"Scraped content length: {len(content)}")
    
    # Multiple URL scraping
    urls = ["https://example.com", "https://httpbin.org/html"]
    results = await scraper.scrape_multiple_urls(urls)
    print(f"Scraped {len(results)} URLs")
    
    # Google search + scraping pipeline
    pipeline_results = await scraper.scrape_and_search_pipeline("Python programming")
    print(f"Pipeline results: {len(pipeline_results)} items")


if __name__ == "__main__":
    # Test the scraper
    asyncio.run(example_usage())