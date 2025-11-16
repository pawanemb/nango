from fastapi import APIRouter, Depends, HTTPException, Path, Request
from app.middleware.auth_middleware import verify_token, verify_request_origin_sync
from app.services.balance_validator import BalanceValidator
from app.models.project import Project
from app.prompts.blogGenerator import outline_prompt
from app.services.normal_outline_generation import OutlineGenerationService
from app.core.logging_config import logger
from typing import Optional, List, Dict, Iterator, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
# 🚀 REMOVED: html2text import - no longer converting HTML to Markdown
import traceback
import requests
import asyncio
import hashlib
from app.services.google_search import google_custom_search
from openai import OpenAI
from app.core.config import settings
import os
from phi.agent import Agent
from phi.tools.googlesearch import GoogleSearch
from phi.workflow import RunResponse, RunEvent
from pydantic import BaseModel, Field
from app.services.search.proxy_google_search import perform_google_search
class GoogleSearchResult(BaseModel):
    title: str = Field(default='', description="Title of the search result")
    link: str = Field(default='', description="URL of the search result")
    snippet: str = Field(default='', description="Snippet or description of the search result")
    traffic_data: dict = Field(default_factory=dict, description="Traffic data for the search result")

from app.services.oxylabs_service import OxylabsService
from app.services.openai_service import OpenAIService
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService

from app.db.session import get_db_session
from fastapi import Request

router = APIRouter()

class OutlineItem(BaseModel):
    text: str

class OutlineSection(BaseModel):
    title: str
    items: List[OutlineItem]


class OutlineGenerationRequest(BaseModel):
    blog_title: str
    primary_keyword: str
    keyword_intent: str
    category: str
    subcategory: str
    word_count: str
    country: str
    industry: Optional[str] = ""
    secondary_keywords: Optional[List[str]] = []

class OutlineResponse(BaseModel):
    status: str
    message: str
    # task_id: str

class OutlineStatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    outlines: Optional[List[Dict]] = None

class AdvancedOutlineGenerationRequest(BaseModel):
    primary_keyword: str
    subcategory: str
    country: str

class ScrapedArticle(BaseModel):
    url: str
    title: str
    content: Optional[str] = None
    outline: Optional[Dict] = None
    outline_number: Optional[int] = None
    traffic_data: Optional[int] = None

class AdvancedOutlineGenerationService:
    def __init__(self, db=None, user_id=None, project_id=None):
        # Initialize usage tracking
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        if db:
            self.llm_usage_service = EnhancedLLMUsageService(db)
            
        # 🚀 PERFORMANCE OPTIMIZATION: Shared resources like EnhancedOutlineCustomizationService
        from concurrent.futures import ThreadPoolExecutor
        self._openai_executor = ThreadPoolExecutor(
            max_workers=8,  # Shared thread pool - no creation overhead
            thread_name_prefix="advanced_outline_worker"
        )
        
        # 🚀 CONNECTION POOLING: For 30% faster HTTP requests
        import aiohttp
        self._http_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=100,          # Total connection pool size
                limit_per_host=20,  # Max connections per host
                keepalive_timeout=30,
                enable_cleanup_closed=True
            ),
            timeout=aiohttp.ClientTimeout(total=10, connect=5),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        
        # 🚀 REDIS CACHING: For 90% faster repeated operations
        from app.core.redis_client import get_redis_client
        import hashlib
        self.redis_client = get_redis_client()
        self.cache_enabled = self.redis_client is not None
        
        # 🚀 FAST ASYNC SCRAPER: Instead of OxylabsService
        from app.services.fast_async_scraper import create_fast_scraper
        self.fast_scraper = create_fast_scraper()
        
        # Keep Oxylabs for fallback
        self.oxylabs_service = OxylabsService()
        
        # OpenAI client
        openai_api_key = settings.OPENAI_API_KEY
        if not openai_api_key:
            openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in settings or environment variables")
            
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.semrush_api_key = settings.SEMRUSH_API_KEY
        self.semrush_api_url = "https://api.semrush.com"
        
        # 🚀 REQUESTS SESSION: With connection pooling for SEMrush API
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def __del__(self):
        """🚀 CLEANUP: Ensure resources are properly closed"""
        try:
            if hasattr(self, '_openai_executor') and self._openai_executor:
                self._openai_executor.shutdown(wait=False)
            if hasattr(self, 'session') and self.session:
                self.session.close()
        except Exception as cleanup_error:
            logger.warning(f"Cleanup warning in AdvancedOutlineGenerationService: {cleanup_error}")
    
    async def _cleanup_async_resources(self):
        """🚀 ASYNC CLEANUP: Clean up async resources"""
        try:
            if hasattr(self, '_http_session') and self._http_session:
                await self._http_session.close()
        except Exception as cleanup_error:
            logger.warning(f"Async cleanup warning: {cleanup_error}")

    def _process_search_results(self, search_results: Any) -> List[GoogleSearchResult]:
        """
        Process raw search results into GoogleSearchResult models
        
        Args:
            search_results: Raw search results from GoogleSearch tool
        
        Returns:
            List of GoogleSearchResult models
        """
        # Enhanced logging for comprehensive debugging
        logger.info(f"Search Results Type: {type(search_results)}")
        logger.info(f"Search Results Raw Content: {search_results}")
        
        # Debug print of all attributes if it's an object
        if hasattr(search_results, '__dict__'):
            logger.info("Search Results Object Attributes:")
            for attr, value in search_results.__dict__.items():
                logger.info(f"  {attr}: {value}")
        
        processed_results = []
        
        try:
            # Specific handling for RunResponse with search results
            if hasattr(search_results, 'content') and isinstance(search_results.content, str):
                logger.info(f"Content Type: {type(search_results.content)}")
                logger.info(f"Content Value: {search_results.content}")
                
                # Check if messages attribute exists and contains search results
                if hasattr(search_results, 'messages') and search_results.messages:
                    for message in search_results.messages:
                        if message.content and 'url' in message.content:
                            try:
                                # Try to parse the content as a JSON array of search results
                                import json
                                search_result_list = json.loads(message.content)
                                
                                processed_results = [
                                    GoogleSearchResult(
                                        title=result.get('title', 'No Title'),
                                        link=result.get('url', ''),
                                        snippet=result.get('description', 'No Description')
                                    ) for result in search_result_list if result.get('url')
                                ]
                                
                                if processed_results:
                                    break
                            except json.JSONDecodeError:
                                logger.error(f"JSON Parsing Error in message: {message.content}")
                
                # Fallback to existing parsing strategies if no results found
                if not processed_results:
                    try:
                        # Strategy 1: Direct JSON parsing
                        urls = json.loads(search_results.content) if isinstance(search_results.content, str) else search_results.content
                        
                        if isinstance(urls, list):
                            processed_results = [
                                GoogleSearchResult(
                                    title='Extracted URL',
                                    link=url,
                                    snippet=f'URL extracted from {type(search_results)}'
                                ) for url in urls if url and isinstance(url, str) and url.startswith('http')
                            ]
                    except (json.JSONDecodeError, TypeError) as json_error:
                        logger.error(f"JSON Parsing Error: {json_error}")
                        
                        # Strategy 2: Regex URL extraction
                        try:
                            import re
                            url_pattern = r'https?://[^\s\'"]+(?=\s|$|\)|\])'
                            urls = re.findall(url_pattern, str(search_results.content))
                            processed_results = [
                                GoogleSearchResult(
                                    title='Regex Extracted URL',
                                    link=url,
                                    snippet=f'URL extracted via regex from {type(search_results)}'
                                ) for url in urls
                            ]
                        except Exception as regex_error:
                            logger.error(f"Regex Extraction Error: {regex_error}")
            
            # Fallback processing for list and dict inputs
            elif isinstance(search_results, list):
                processed_results = [
                    GoogleSearchResult(
                        title=result.get('title', 'No Title'),
                        link=result.get('url', result.get('link', '')),
                        snippet=result.get('description', result.get('snippet', 'No Description'))
                    ) for result in search_results if result.get('url') or result.get('link')
                ]
            
            elif isinstance(search_results, dict):
                results_list = search_results.get('results', [])
                processed_results = [
                    GoogleSearchResult(
                        title=result.get('title', 'No Title'),
                        link=result.get('url', result.get('link', '')),
                        snippet=result.get('description', result.get('snippet', 'No Description'))
                    ) for result in results_list if result.get('url') or result.get('link')
                ]
        
        except Exception as general_error:
            logger.error(f"Unexpected Error in Search Result Processing: {general_error}")
            logger.error(f"Full Error Details: {traceback.format_exc()}")
        
        # Final logging of processed results
        if not processed_results:
            logger.warning("NO SEARCH RESULTS COULD BE PROCESSED")
            logger.warning(f"Original Input Type: {type(search_results)}")
            logger.warning(f"Original Input Content: {search_results}")
        else:
            logger.info(f"Successfully Processed {len(processed_results)} Search Results")
            for result in processed_results:
                logger.info(f"Processed Result - Link: {result['link']}")
        
        return processed_results

    def _clean_and_convert_to_markdown(self, content: str) -> str:
        """
        Clean and preserve RAW HTML content - NO MARKDOWN CONVERSION
        
        Args:
            content (str): Raw scraped content
        
        Returns:
            str: Cleaned RAW HTML content
        """
        if not content:
            return ""
        
        try:
            import re
            from bs4 import BeautifulSoup
            
            # 🚀 REMOVED MARKDOWN CONVERSION: Keep raw HTML structure
            # Parse HTML with BeautifulSoup for cleaning
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove unwanted elements but keep HTML structure
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
                element.decompose()
            
            # Remove comments
            from bs4 import Comment
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # Clean raw HTML while preserving structure
            raw_html = str(soup)
            
            # Clean up excessive whitespace while preserving HTML structure
            raw_html = re.sub(r'\n\s*\n', '\n', raw_html)  # Multiple newlines to single
            raw_html = re.sub(r' +', ' ', raw_html)  # Multiple spaces to single
            
            # Remove non-printable characters except common whitespace
            import string
            cleaned_html = ''.join(char for char in raw_html if char.isprintable() or char in '\n\t ')
            
            # Final cleanup
            cleaned_html = re.sub(r'\n{3,}', '\n\n', cleaned_html)  # Max 2 consecutive newlines
            
            # Remove leading/trailing whitespace
            cleaned_html = cleaned_html.strip()
            
            # Limit content length if it's extremely long
            max_length = 100000  # Adjust as needed
            if len(cleaned_html) > max_length:
                cleaned_html = cleaned_html[:max_length] + "\n\n[Content truncated]"
            
            logger.info(f"RAW HTML cleaning - Original length: {len(content)}, Cleaned HTML length: {len(cleaned_html)}")
            
            return cleaned_html
        
        except Exception as e:
            logger.error(f"Error cleaning HTML content: {str(e)}")
            return content  # Fallback to original content if cleaning fails

    def generate_outline_from_gpt(self, scrapped_content: str, usage_tracker: Optional[Dict] = None) -> Dict:
        # Use OpenAI to generate outline
        from app.prompts.blogGenerator.outline.outline_website import outline_website_prompt
        
        # Generate the prompt for the specific scrapped content
        outline_prompt = outline_website_prompt(scrapped_content)
            
        # Use ChatGPT to generate the outline
        outline = self.openai_client.responses.create(
            model=settings.OPENAI_MODEL,  # or gpt-4 if available
            input=[
                {"role": "system", "content": "You are an expert content strategist and outline generator."},
                {"role": "user", "content": outline_prompt}
            ],
            max_output_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE
        )
        
        # 🔥 COMBINED USAGE TRACKING: Accumulate tokens instead of individual recording
        if usage_tracker is not None:
            usage_tracker["total_input_tokens"] += outline.usage.input_tokens
            usage_tracker["total_output_tokens"] += outline.usage.output_tokens
            usage_tracker["total_calls"] += 1
            usage_tracker["individual_calls"].append({
                "call_number": usage_tracker["total_calls"],
                "content_source": "scraped_website",
                "content_length": len(scrapped_content),
                "prompt_type": "outline_from_scraped_content",
                "input_tokens": outline.usage.input_tokens,
                "output_tokens": outline.usage.output_tokens,
                "model_name": outline.model
            })
            
            logger.info(f"📊 Advanced outline call #{usage_tracker['total_calls']}: "
                       f"{outline.usage.input_tokens} input + {outline.usage.output_tokens} output tokens "
                       f"(Running total: {usage_tracker['total_input_tokens']} input, "
                       f"{usage_tracker['total_output_tokens']} output)")
        
        # Extract text content from ChatCompletion
        outline_text = outline.output_text
        
        # Parse the outline response 
        # Assuming the response is a JSON or can be converted to a dictionary
        parsed_outline = self._parse_outline_response(outline_text)
        
        return parsed_outline

    def _parse_outline_response(self, gpt_response: str) -> Dict:
        """
        Parse the GPT response into a structured outline.
        Handles the specific JSON format with sections, subheadings, conclusion, and FAQs.
        """
        try:
            # Attempt to parse the response as JSON
            import json
            parsed_outline = json.loads(gpt_response)
            
            # Validate the structure
            if not isinstance(parsed_outline, dict):
                logger.error("Parsed outline is not a dictionary")
                return {}
            
            # Ensure we have a sections key with a list of sections
            if 'sections' not in parsed_outline or not isinstance(parsed_outline['sections'], list):
                logger.error("No valid sections found in the outline")
                return {}
            
            # Extract sections with headings and subheadings
            sections = []
            for section in parsed_outline.get('sections', []):
                if 'heading' in section:
                    sections.append({
                        "heading": section['heading'],
                        "subsections": section.get('subsections', [])
                    })
            
            # Construct the final outline structure
            outline = {
                "sections": sections,
                "conclusion": parsed_outline.get('conclusion', ''),
                "faqs": parsed_outline.get('faqs', [])
            }
            
            return outline
        
        except json.JSONDecodeError:
            # If JSON parsing fails, log the error and return an empty dict
            logger.error(f"Failed to parse outline JSON. Response: {gpt_response}")
            return {}
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error parsing outline: {str(e)}")
            return {}

    def _extract_sections(self, outline_text: str) -> List[Dict]:
        """
        Extract sections from the outline text.
        This is a basic implementation and might need refinement.
        """
        sections = []
        # Split by markdown headers or use regex to extract sections
        import re
        section_pattern = r'(#{1,2}\s*[^\n]+)\n((?:- [^\n]+\n)*)'
        matches = re.findall(section_pattern, outline_text)
        
        for title, items_text in matches:
            items = [
                {"text": item.strip('- ')} 
                for item in items_text.split('\n') 
                if item.strip()
            ]
            sections.append({
                "title": title.strip('# '),
                "items": items
            })
        
        return sections

    async def _get_traffic_data_async(self, search_results: List[Dict]) -> Dict[str, int]:
        """
        🚀 ASYNC SEMRUSH: Fetch traffic data in parallel for all URLs using async HTTP
        
        Args:
            search_results: List of search results containing URLs.
        
        Returns:
            Dictionary mapping URLs to their total traffic data.
        """
        traffic_data = {}
        
        if not self.semrush_api_key:
            logger.warning("No SEMrush API key - skipping traffic data")
            return traffic_data
        
        # ⚡ PARALLEL API CALLS: Process all URLs simultaneously
        traffic_tasks = []
        
        for result in search_results:
            url = result["link"]
            
            # Check Redis cache first
            cache_key = f"semrush_traffic:{hashlib.md5(url.encode()).hexdigest()}"
            if self.cache_enabled:
                try:
                    cached_traffic = self.redis_client.get(cache_key)
                    if cached_traffic:
                        traffic_value = cached_traffic.decode('utf-8') if isinstance(cached_traffic, bytes) else cached_traffic
                        traffic_data[url] = int(traffic_value)
                        logger.info(f"✅ TRAFFIC CACHE HIT: {url[:50]}...")
                        continue
                except Exception as cache_error:
                    logger.warning(f"Traffic cache read failed for {url}: {cache_error}")
            
            # Create async task for API call
            traffic_tasks.append(self._fetch_single_url_traffic(url, cache_key))
        
        # Execute all traffic API calls in parallel
        if traffic_tasks:
            traffic_results = await asyncio.gather(*traffic_tasks, return_exceptions=True)
            
            for i, traffic_result in enumerate(traffic_results):
                url = search_results[i]["link"]
                if isinstance(traffic_result, int):
                    traffic_data[url] = traffic_result
                elif isinstance(traffic_result, Exception):
                    logger.error(f"Traffic fetch failed for {url}: {traffic_result}")
                    traffic_data[url] = 0
        
        # Add traffic data to search results
        for result in search_results:
            result["traffic_data"] = traffic_data.get(result["link"], 0)
        
        logger.info(f"🚀 PARALLEL TRAFFIC: Processed {len(traffic_data)} URLs")
        return traffic_data
    
    async def _fetch_single_url_traffic(self, url: str, cache_key: str) -> int:
        """
        🚀 Async fetch traffic data for single URL with caching
        """
        try:
            params = {
                "key": self.semrush_api_key,
                "type": "subfolder_ranks",
                "export_columns": "Db,Ot",
                "subfolder": url
            }
            
            # Use aiohttp for async HTTP request
            async with self._http_session.get(self.semrush_api_url, params=params) as response:
                if response.status == 200:
                    response_text = await response.text()
                    total_clicks = 0
                    
                    # Parse CSV response
                    for line in response_text.strip().split("\n")[1:]:  # Skip header
                        if ";" in line:
                            try:
                                db, ot = line.split(";")
                                clicks = int(ot.strip())
                                total_clicks += clicks
                            except (ValueError, IndexError):
                                continue
                    
                    # Cache the result for 6 hours
                    if self.cache_enabled and total_clicks > 0:
                        try:
                            self.redis_client.setex(cache_key, 21600, str(total_clicks))
                        except Exception as cache_error:
                            logger.warning(f"Traffic cache write failed: {cache_error}")
                    
                    logger.info(f"✅ TRAFFIC: {url[:50]}... = {total_clicks} clicks")
                    return total_clicks
                else:
                    logger.warning(f"SEMrush API error {response.status} for {url}")
                    return 0
                    
        except Exception as api_error:
            logger.error(f"Traffic API call failed for {url}: {api_error}")
            return 0

    async def _scrape_articles_streaming(self, search_results: List[Dict], usage_tracker: Dict) -> List[ScrapedArticle]:
        """
        🚀 STREAMING PIPELINE: Async scraping with FastAsyncScraper + parallel OpenAI processing
        
        Args:
            search_results: List of search result dictionaries
            usage_tracker: Combined usage tracking dictionary
        
        Returns:
            List of scraped articles with outlines
        """
        logger.info(f"🚀 STREAMING MODE: Starting async scraping pipeline for {len(search_results)} articles")
        
        scraped_articles = []
        
        # ⚡ STREAMING PIPELINE: Google → FastAsyncScraper → OpenAI all in parallel
        scraping_tasks = []
        for index, result in enumerate(search_results[:5]):
            url = result["link"]
            cache_key = f"outline_scrape:{hashlib.md5(url.encode()).hexdigest()}"
            
            # Check Redis cache first (90% faster on cache hits)
            if self.cache_enabled:
                try:
                    cached_content = self.redis_client.get(cache_key)
                    if cached_content:
                        logger.info(f"✅ CACHE HIT: {url[:50]}...")
                        content_str = cached_content.decode('utf-8') if isinstance(cached_content, bytes) else cached_content
                        scraped_article = ScrapedArticle(
                            url=url,
                            title=result['title'],
                            content=content_str,
                            outline_number=index + 1,
                            traffic_data=result.get('traffic_data', {})
                        )
                        scraped_articles.append(scraped_article)
                        continue
                except Exception as cache_error:
                    logger.warning(f"Cache read failed for {url}: {cache_error}")
            
            # ⚡ FastAsyncScraper for 60% faster scraping
            scraping_tasks.append(
                self._async_scrape_single_url(url, result, index + 1, cache_key)
            )
        
        # Execute all scraping tasks in parallel
        if scraping_tasks:
            scraped_results = await asyncio.gather(*scraping_tasks, return_exceptions=True)
            
            for result in scraped_results:
                if isinstance(result, ScrapedArticle):
                    scraped_articles.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Scraping task failed: {result}")
        
        # ⚡ PARALLEL OpenAI OUTLINE GENERATION using shared thread pool
        outline_tasks = []
        for article in scraped_articles:
            if article.content and len(article.content.strip()) > 100:
                logger.info(f"🤖 PREPARING OPENAI: {article.url[:50]}... ({len(article.content)} chars)")
                # Use shared thread pool instead of creating new ones
                outline_tasks.append(
                    asyncio.get_event_loop().run_in_executor(
                        self._openai_executor,
                        self.generate_outline_from_gpt,
                        article.content,
                        usage_tracker
                    )
                )
            else:
                logger.warning(f"⚠️ SKIPPING OPENAI: {article.url[:50]}... (insufficient content: {len(article.content) if article.content else 0} chars)")
        
        if outline_tasks:
            logger.info(f"🤖 EXECUTING {len(outline_tasks)} OpenAI tasks in parallel...")
            outline_results = await asyncio.gather(*outline_tasks, return_exceptions=True)
            
            # Map results back to articles that had content
            articles_with_content = [a for a in scraped_articles if a.content and len(a.content.strip()) > 100]
            
            for i, outline_result in enumerate(outline_results):
                if i < len(articles_with_content):
                    article = articles_with_content[i]
                    if isinstance(outline_result, dict):
                        # Add metadata to outline
                        outline_result['url'] = article.url
                        outline_result['outline_number'] = article.outline_number
                        outline_result['traffic_data'] = article.traffic_data
                        article.outline = outline_result
                        logger.info(f"✅ OPENAI SUCCESS: {article.url[:50]}... | Keys: {list(outline_result.keys())}")
                    elif isinstance(outline_result, Exception):
                        logger.error(f"❌ OPENAI FAILED: {article.url}: {outline_result}")
                        article.outline = None
                    else:
                        logger.warning(f"⚠️ OPENAI UNEXPECTED: {article.url}: {type(outline_result)} - {str(outline_result)[:100]}")
                        article.outline = outline_result  # Store whatever we got
        else:
            logger.warning("⚠️ NO OPENAI TASKS: No articles had sufficient content for processing")
        
        # 📈 DETAILED DEBUGGING: Log what we got
        articles_with_content = [a for a in scraped_articles if a.content and len(a.content.strip()) > 100]
        articles_with_outlines = [a for a in scraped_articles if hasattr(a, 'outline') and a.outline]
        
        logger.info(f"🚀 STREAMING COMPLETE: {len(scraped_articles)} total articles, {len(articles_with_content)} with content, {len(articles_with_outlines)} with outlines")
        
        for i, article in enumerate(scraped_articles):
            content_status = f"{len(article.content)} chars" if article.content else "NO CONTENT"
            outline_status = "HAS OUTLINE" if hasattr(article, 'outline') and article.outline else "NO OUTLINE"
            logger.info(f"  Article {i+1}: {article.url[:50]}... | {content_status} | {outline_status}")
        
        return scraped_articles
    
    async def _async_scrape_single_url(self, url: str, result_data: Dict, outline_number: int, cache_key: str) -> ScrapedArticle:
        """
        🚀 Async scrape single URL with FastAsyncScraper and Redis caching
        """
        try:
            # Use FastAsyncScraper for high-performance async scraping
            scraped_content = await self.fast_scraper.scrape_url(url)
            
            if scraped_content:
                # Clean content
                cleaned_content = self._clean_and_convert_to_markdown(scraped_content)
                
                # Cache the cleaned content for 1 hour
                if self.cache_enabled and cleaned_content:
                    try:
                        self.redis_client.setex(cache_key, 3600, cleaned_content.encode('utf-8'))
                        logger.info(f"📦 Cached content for: {url[:50]}...")
                    except Exception as cache_error:
                        logger.warning(f"Cache write failed for {url}: {cache_error}")
                
                logger.info(f"✅ FAST SCRAPE: {url[:50]}... ({len(cleaned_content)} chars)")
                
                return ScrapedArticle(
                    url=url,
                    title=result_data['title'],
                    content=cleaned_content,
                    outline_number=outline_number,
                    traffic_data=result_data.get('traffic_data', {})
                )
            else:
                logger.warning(f"⚠️ No content scraped from: {url}")
                return ScrapedArticle(
                    url=url,
                    title=result_data['title'],
                    content="",
                    outline_number=outline_number,
                    traffic_data=result_data.get('traffic_data', {})
                )
                
        except Exception as scrape_error:
            logger.error(f"❌ Scraping failed for {url}: {scrape_error}")
            # Return empty article so processing can continue
            return ScrapedArticle(
                url=url,
                title=result_data['title'],
                content="",
                outline_number=outline_number,
                traffic_data=result_data.get('traffic_data', {})
            )

    async def generate_advanced_outline(self, primary_keyword: str, subcategory: str, country: str) -> Dict:
        """
        Generate advanced outline by searching, scraping, and generating outlines
        
        Args:
            primary_keyword: Primary keyword for the search
            subcategory: Subcategory to refine the search
        
        Returns:
            Dictionary with outline generation results
        """
        # Log input parameters
        logger.info(f"Generating advanced outline")
        logger.info(f"Primary Keyword: {primary_keyword}")
        logger.info(f"Subcategory: {subcategory}")
        logger.info(f"Country: {country}")
        
        # 🔥 COMBINED USAGE TRACKING: Initialize tracker for all OpenAI calls
        import uuid
        usage_tracker = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_calls": 0,
            "service_name": "outline_generation_suggestion",
            "request_id": str(uuid.uuid4())[:8],
            "individual_calls": []  # Track each individual call details
        }
        
        # Step 1: Search for relevant articles
        search_query = f"{subcategory} {primary_keyword}"
        logger.info(f"Search Query: {search_query}")
        
        # Run the search and process results
        # search_results = self.google_searcher.run(search_query)

        search_results = []
        try:
            # search_results = google_custom_search(
            #     query=search_query,
            #     api_key=settings.GOOGLE_API_KEY,
            #     search_engine_id=settings.GOOGLE_CSE_ID
            # )
            search_results = perform_google_search(
                query=search_query,
                num_results=5,
                lang="en",
                country=country,
                proxy=settings.OXYLABS_PROXY_URL,
                # Use default proxy
                timeout=30,
                retry_count=3
            )
            logger.info(f"Found {len(search_results)} search results")
        except Exception as search_error:
            logger.error(f"Error during Google search: {str(search_error)}")
        
        # Format search results
        formatted_results = []
        logger.info(f"Search results type: {type(search_results)}")
        logger.info(f"Number of search results: {len(search_results)}")
        
        for result in search_results:
            try:
                # Convert GoogleSearchResult object to dictionary
                formatted_results.append({
                    "title": result.title,
                    "link": result.url,  # Note: using url instead of link
                    "content": result.description,  # Note: using description instead of snippet
                    # "datePublished": str(result.date_published) if result.date_published else None
                })
            except Exception as format_error:
                logger.error(f"Error formatting search result: {str(format_error)}")
                continue

        logger.info("----------------------------------------------------")
        logger.info("----------------------------------------------------")
        logger.info(f"Raw search results type: {type(formatted_results)}")
        logger.info(f"Raw search results content: {formatted_results}")
        logger.info("----------------------------------------------------")
        logger.info("----------------------------------------------------")
        
        # processed_search_results = self._process_search_results(formatted_results)

        # Convert formatted search results to GoogleSearchResult objects
        # processed_search_results = [
        #     GoogleSearchResult(
        #         title=result["title"],
        #         link=result["link"],
        #         snippet=result["content"]
        #     )
        #     for result in formatted_results
        # ]

        # Step 2: Process search results
        #processed_search_results = self._process_search_results(formatted_results)

        # Step 3: 🚀 ASYNC TRAFFIC DATA - Fetch traffic data in parallel
        try:
            await self._get_traffic_data_async(formatted_results)
        except Exception as exc:
            logger.error(f"Error fetching traffic data: {str(exc)}")

        # Step 4: 🚀 STREAMING PIPELINE - Async scraping + parallel OpenAI
        logger.info("----------------------------------------------------")
        logger.info(f"Formatted results: {formatted_results}")
        scraped_articles = await self._scrape_articles_streaming(formatted_results, usage_tracker)

        # Step 5: 📊 DETAILED OUTLINE VALIDATION
        valid_outlines = []
        invalid_outlines = []
        
        for article in scraped_articles:
            if hasattr(article, 'outline') and article.outline:
                # Check multiple possible outline structures (be more flexible)
                if (isinstance(article.outline, dict) and 
                    (article.outline.get('sections') or 
                     article.outline.get('outline') or 
                     article.outline.get('headings') or
                     len(article.outline.keys()) > 0)):
                    valid_outlines.append(article.outline)
                    logger.info(f"✅ VALID OUTLINE: {article.url[:50]}... | Keys: {list(article.outline.keys()) if isinstance(article.outline, dict) else 'Not dict'}")
                else:
                    invalid_outlines.append(article.outline)
                    logger.warning(f"❌ INVALID OUTLINE: {article.url[:50]}... | Content: {str(article.outline)[:100]}...")
            else:
                invalid_outlines.append(None)
                logger.warning(f"❌ NO OUTLINE: {article.url[:50]}...")
        
        logger.info(f"📈 OUTLINE SUMMARY: {len(valid_outlines)} valid, {len(invalid_outlines)} invalid/missing")
        
        # 📝 DETAILED LOGGING
        logger.info("=== OUTLINE GENERATION RESULTS ===")
        for i, outline in enumerate(valid_outlines):
            logger.info(f"Valid Outline {i+1}: {str(outline)[:200]}...")
        
        if invalid_outlines:
            logger.info("=== INVALID/MISSING OUTLINES ===")
            for i, outline in enumerate(invalid_outlines[:3]):  # Limit to first 3
                logger.info(f"Invalid {i+1}: {str(outline)[:100]}...")
        
        # 🔥 COMBINED BILLING: Record single usage entry for all OpenAI calls
        if usage_tracker["total_calls"] > 0 and hasattr(self, 'llm_usage_service') and self.llm_usage_service:
            try:
                advanced_metadata = {
                    "advanced_outline_stats": {
                        "total_openai_calls": usage_tracker["total_calls"],
                        "total_articles_processed": len(scraped_articles),
                        "valid_outlines_generated": len(valid_outlines),
                        "request_id": usage_tracker["request_id"],
                        "primary_keyword": primary_keyword,
                        "subcategory": subcategory,
                        "country": country,
                        "search_query": search_query
                    },
                    "individual_openai_calls": usage_tracker["individual_calls"]  # ALL individual call details
                }
                
                # Record combined usage with advanced service multiplier (5.0x)
                billing_result = self.llm_usage_service.record_llm_usage(
                    user_id=self.user_id,
                    service_name=usage_tracker["service_name"],  # "outline_generation_suggestion"
                    model_name=settings.OPENAI_MODEL,  # Use model name from settings
                    input_tokens=usage_tracker["total_input_tokens"],
                    output_tokens=usage_tracker["total_output_tokens"],
                    service_description=f"Advanced outline generation - {usage_tracker['total_calls']} OpenAI calls combined",
                    project_id=self.project_id,
                    additional_metadata=advanced_metadata
                )
                
                logger.info(f"✅ ADVANCED OUTLINE BILLING RECORDED: {usage_tracker['total_calls']} calls, "
                           f"${billing_result.get('cost', 0):.6f} charged with 5.0x multiplier")
                
            except Exception as e:
                logger.error(f"❌ Failed to record advanced outline usage: {e}")
        else:
            logger.warning("No OpenAI calls were made during advanced outline generation")
        
        # 📈 FINAL RESULTS
        logger.info(f"🏁 FINAL RESULTS: {len(valid_outlines)} valid outlines from {len(scraped_articles)} articles")
        
        if valid_outlines:
            return {
                "status": "success",
                "message": f"🚀 STREAMING SUCCESS: Generated {len(valid_outlines)} outlines with async pipeline - {len(scraped_articles)} articles processed with parallel scraping + OpenAI",
                "outlines": valid_outlines
            }
        else:
            # 🔍 DEBUG: If no valid outlines, let's see what we actually got
            debug_info = []
            for i, article in enumerate(scraped_articles):
                article_info = {
                    "url": article.url[:50],
                    "content_length": len(article.content) if article.content else 0,
                    "has_outline_attr": hasattr(article, 'outline'),
                    "outline_type": type(article.outline).__name__ if hasattr(article, 'outline') else 'None',
                    "outline_content": str(article.outline)[:100] if hasattr(article, 'outline') and article.outline else 'None'
                }
                debug_info.append(article_info)
            
            logger.warning(f"🔍 DEBUG INFO: {debug_info}")
            
            # Fallback - return what we have if there's any content
            any_outlines = [a.outline for a in scraped_articles if hasattr(a, 'outline') and a.outline]
            if any_outlines:
                logger.info(f"🔄 FALLBACK: Returning {len(any_outlines)} raw outlines (validation failed but content exists)")
                return {
                    "status": "success",
                    "message": f"🔄 PARTIAL SUCCESS: Generated {len(any_outlines)} outlines (some validation issues) from {len(scraped_articles)} articles",
                    "outlines": any_outlines
                }
            
            logger.warning("No valid outlines could be generated")
            return {
                "status": "error",
                "message": f"❌ No valid outlines generated - {len(scraped_articles)} articles processed, check logs for details",
                "outlines": []
            }

@router.post("/")
def generate_blog_outline(
    request: Request,
    *,
    outline_generation_request: OutlineGenerationRequest,
):
    """Generate SEO-optimized blog outline."""
    # logger.debug(f"Generating outline for project_id: {project_id}, primary_keyword: {outline_generation_request.primary_keyword}")
    project_id = request.path_params.get("project_id")

    try:    
        # Verify authentication
        user = verify_token_sync(request)
        current_user_id = user.user.id
        
        # Verify project exists
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project not found with id: {project_id}"
                )
            
            # Verify project ownership
            if str(project.user_id) != str(current_user_id):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this project"
                )
        
            # Start the outline generation task with proper parameters
            service = OutlineGenerationService(db=db, user_id=current_user_id, project_id=project_id)
            result = service.generate_blog_outline(
                blog_title=outline_generation_request.blog_title,
                primary_keyword=outline_generation_request.primary_keyword,
                secondary_keywords=outline_generation_request.secondary_keywords or [],
                keyword_intent=outline_generation_request.keyword_intent,
                industry=outline_generation_request.industry or "",
                word_count=outline_generation_request.word_count,
                category=outline_generation_request.category,
                country=outline_generation_request.country,
                subcategory=outline_generation_request.subcategory,
                project_id=project_id
            )
        
        return {
            "status": "success",
            "message": "Outline generated successfully",
            "data": result,
        }
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error in outline generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        logger.info("Finished generate_blog_outline outline")


@router.post("/new")
def generate_blog_outline(
    request: Request,
    *,
    outline_generation_request: OutlineGenerationRequest,
    current_user = Depends(verify_request_origin_sync)
):
    """Generate SEO-optimized blog outline."""
    # logger.debug(f"Generating outline for project_id: {project_id}, primary_keyword: {outline_generation_request.primary_keyword}")
    project_id = request.path_params.get("project_id")

    try:    
        # Get user ID from nested user object
        current_user_id = current_user.user.id
        
        # Verify project exists
        project = None
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="outline_generation"
            )
            
            if not balance_check["valid"]:
                if balance_check["error"] == "insufficient_balance":
                    raise HTTPException(
                        status_code=402,  # Payment Required
                        detail={
                            "error": "insufficient_balance",
                            "message": balance_check["message"],
                            "required_balance": balance_check["required_balance"],
                            "current_balance": balance_check["current_balance"],
                          "shortfall": balance_check["shortfall"],
                              "next_refill_time": balance_check.get("next_refill_time").isoformat() if balance_check.get("next_refill_time") else None                       }
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": balance_check["error"],
                            "message": balance_check["message"]
                        }
                    )
            
            logger.info(f"✅ Balance validation passed for user {current_user_id}: ${balance_check['current_balance']:.2f} >= ${balance_check['required_balance']:.2f}")
            
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project not found with id: {project_id}"
                )
            
            # Verify project ownership
            if str(project.user_id) != str(current_user_id):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this project"
                )
        
            # Log incoming API request parameters including country
            logger.info(f"=== OUTLINE GENERATION API (/new) - INCOMING REQUEST ===")
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Blog title: {outline_generation_request.blog_title}")
            logger.info(f"Primary keyword: {outline_generation_request.primary_keyword}")
            logger.info(f"Country parameter: {outline_generation_request.country}")
            logger.info(f"Category: {outline_generation_request.category}")
            logger.info(f"Subcategory: {outline_generation_request.subcategory}")
            
            # Start the outline generation task with proper parameters
            service = OutlineGenerationService(db=db, user_id=current_user_id, project_id=project_id)
            logger.info(project.to_dict())
            result = service.generate_blog_outline_updated(
                blog_title=outline_generation_request.blog_title,
                primary_keyword=outline_generation_request.primary_keyword,
                secondary_keywords=outline_generation_request.secondary_keywords or [],
                keyword_intent=outline_generation_request.keyword_intent,
                industry=outline_generation_request.industry or "",
                word_count=outline_generation_request.word_count,
                category=outline_generation_request.category,
                country=outline_generation_request.country,
                subcategory=outline_generation_request.subcategory,
                project_id=project_id,
                project=project.to_dict()
            )
        
        return {
            "status": "success",
            "message": "Outline generated successfully",
            "data": result,
            # "task_id": None  # Added to maintain compatibility with existing frontend
        }
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error in outline generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        logger.info("Finished generate_blog_outline outline")



@router.post("/advanced-outline")
async def generate_advanced_outline(
    request: Request,
    *,
    advanced_outline_request: AdvancedOutlineGenerationRequest,
    current_user = Depends(verify_request_origin_sync)
):
    """🚀 STREAMING: Generate advanced blog outline using async web research and parallel AI processing."""
    try:
        # Get user ID from nested user object
        current_user_id = current_user.user.id
        
        # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
        with get_db_session() as db:
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="outline_generation_suggestion"
            )
            
            if not balance_check["valid"]:
                if balance_check["error"] == "insufficient_balance":
                    raise HTTPException(
                        status_code=402,  # Payment Required
                        detail={
                            "error": "insufficient_balance",
                            "message": balance_check["message"],
                            "required_balance": balance_check["required_balance"],
                            "current_balance": balance_check["current_balance"],
                          "shortfall": balance_check["shortfall"],
                              "next_refill_time": balance_check.get("next_refill_time").isoformat() if balance_check.get("next_refill_time") else None                       }
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": balance_check["error"],
                            "message": balance_check["message"]
                        }
                    )
            
            logger.info(f"✅ Balance validation passed for user {current_user_id}: ${balance_check['current_balance']:.2f} >= ${balance_check['required_balance']:.2f}")
            
            # Get project ID from request path
            project_id = request.path_params.get("project_id")
            
            # Initialize service with streaming architecture
            advanced_outline_service = AdvancedOutlineGenerationService(
                db=db,
                user_id=current_user_id,
                project_id=project_id
            )
            
            # 🚀 STREAMING PIPELINE: Async processing with parallel operations
            result = await advanced_outline_service.generate_advanced_outline(
                primary_keyword=advanced_outline_request.primary_keyword,
                subcategory=advanced_outline_request.subcategory,
                country=advanced_outline_request.country
            )
            
            # 🚀 CLEANUP: Close async resources
            await advanced_outline_service._cleanup_async_resources()
        
        return OutlineStatusResponse(**result)
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error generating advanced outline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))