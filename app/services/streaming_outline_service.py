"""
🚀 Streaming Outline Generation Service
Real-time streaming pipeline with parallel processing and OpenAI streaming
"""

import asyncio
import json
import uuid
from typing import AsyncGenerator, Dict, List, Optional, Any
from datetime import datetime
import aiohttp
# WebSocket import removed - not used
from app.core.config import settings
from app.core.logging_config import logger
# Redis removed - keeping it simple
from app.services.fast_async_scraper import create_fast_scraper

# Import RayoScraper for website scraping
try:
    from app.services.rayo_scraper import RayoScrapingService
    RAYO_SCRAPER_AVAILABLE = True
    logger.info("✅ RayoScraper available for streaming outline service")
except ImportError as e:
    RAYO_SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️ RayoScraper not available: {e}")
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
from openai import AsyncOpenAI
# hashlib removed - keeping it simple


class StreamingOutlineService:
    """
    🚀 STREAMING ARCHITECTURE: Real-time outline generation with parallel pipelines
    """
    
    def __init__(self, db=None, user_id=None, project_id=None):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
# Redis removed - keeping it simple
        self.fast_scraper = create_fast_scraper()
        
        # Initialize RayoScraper for website content extraction
        self.rayo_scraper = RayoScrapingService(user_id=user_id or "streaming-outline") if RAYO_SCRAPER_AVAILABLE else None
        
        # Store tracking IDs for scraping
        self.current_blog_id = None
        
        # OpenAI async client for streaming
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Usage tracking
        if db:
            self.llm_usage_service = EnhancedLLMUsageService(db)
        
        # SEMrush configuration
        self.semrush_api_key = settings.SEMRUSH_API_KEY
        self.semrush_api_url = "https://api.semrush.com"
        
        # HTTP session for API calls
        self.http_session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.http_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                keepalive_timeout=30
            ),
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.http_session:
            await self.http_session.close()

    async def stream_outline_generation(
        self, 
        primary_keyword: str, 
        subcategory: str, 
        country: str,
        blog_id: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        🎯 SIMPLE STREAMING: Search → Traffic → Scrape each → Outline each → Done
        """
        
        try:
            # Set blog_id for tracking
            self.current_blog_id = blog_id
            
            # Step 1: Search
            yield {"status": "searching", "message": "Searching for websites..."}
            
            search_results = await self._perform_search(primary_keyword, subcategory, country)
            
            # Step 2: Get traffic data for all sites
            traffic_data = await self._get_traffic_data_parallel(search_results)
            
            # Update search results with traffic
            for result in search_results:
                result["traffic_data"] = traffic_data.get(result["url"], 0)
            
            # Step 3: Show found websites with traffic
            yield {
                "status": "found_websites",
                "message": f"Found {len(search_results)} websites",
                "data": {
                    "traffic_summary": [
                        {
                            "number": i,
                            "url": result["url"],
                            "title": result["title"],
                            "traffic": result.get("traffic_data", 0)
                        } for i, result in enumerate(search_results, 1)
                    ],
                    "total_traffic": sum(result.get("traffic_data", 0) for result in search_results)
                }
            }
            
            # Step 4: MAXIMUM PARALLEL PROCESSING - All scraping + AI in parallel
            yield {"status": "processing_start", "message": "Processing started"}
            
            # Create a queue for managing parallel AI tasks
            ai_tasks = {}
            completed_outlines = []
            
            # Start ALL scraping tasks immediately in parallel
            scraping_tasks = {}
            for i, result in enumerate(search_results, 1):
                scrape_task = asyncio.create_task(self._scrape_single_website(result["url"]))
                scraping_tasks[scrape_task] = {"result": result, "number": i}
            
            # Process completions as they happen
            all_tasks = set(scraping_tasks.keys())
            
            while all_tasks or ai_tasks:
                # Wait for any task to complete
                if all_tasks:
                    done_tasks, pending_tasks = await asyncio.wait(
                        all_tasks | set(ai_tasks.keys()),
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    all_tasks = pending_tasks & all_tasks
                else:
                    # Only AI tasks remaining
                    done_tasks, pending_tasks = await asyncio.wait(
                        set(ai_tasks.keys()),
                        return_when=asyncio.FIRST_COMPLETED
                    )
                
                # Process completed tasks
                for task in done_tasks:
                    try:
                        if task in scraping_tasks:
                            # Scraping completed - immediately start AI (NO STREAMING EVENT)
                            content = await task
                            website_info = scraping_tasks[task]
                            result = website_info["result"]
                            number = website_info["number"]
                            
                            if content and len(content.strip()) >= 100:
                                # Start AI generation immediately (silently)
                                ai_task = asyncio.create_task(self._generate_single_outline(content))
                                ai_tasks[ai_task] = {
                                    "result": result,
                                    "number": number,
                                    "content": content
                                }
                            else:
                                # No AI needed - report failure immediately
                                yield {
                                    "status": "website_failed",
                                    "message": f"Website {number} failed - insufficient content",
                                    "url": result["url"]
                                }
                            
                            del scraping_tasks[task]
                            
                        elif task in ai_tasks:
                            # AI generation completed - STREAM WEBSITE COMPLETE
                            outline = await task
                            website_info = ai_tasks[task]
                            result = website_info["result"]
                            number = website_info["number"]
                            
                            website_data = {
                                "url": result["url"],
                                "title": result["title"],
                                "traffic": result.get("traffic_data", 0),
                                "number": number,
                                "outline": outline
                            }
                            
                            completed_outlines.append(website_data)
                            
                            yield {
                                "status": "website_complete",
                                "message": f"Website {number} complete! ({len(completed_outlines)}/{len(search_results)})",
                                "data": website_data
                            }
                            
                            del ai_tasks[task]
                            
                    except Exception as e:
                        # Handle errors for both scraping and AI tasks
                        if task in scraping_tasks:
                            website_info = scraping_tasks[task]
                            del scraping_tasks[task]
                        elif task in ai_tasks:
                            website_info = ai_tasks[task]
                            del ai_tasks[task]
                        else:
                            website_info = {"number": "unknown"}
                        
                        yield {
                            "status": "website_error",
                            "message": f"Website {website_info.get('number', 'unknown')} error: {str(e)}"
                        }
            
            # Use completed outlines instead of the old outlines list
            outlines = completed_outlines
            
            # Save streaming outlines to MongoDB as outlines.advanced
            if completed_outlines and blog_id:
                try:
                    from app.services.mongodb_service import MongoDBService
                    from bson import ObjectId
                    import pytz
                    
                    mongodb_service = MongoDBService()
                    mongodb_service.init_sync_db()
                    
                    # Prepare streaming outline data for outlines.advanced
                    current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
                    
                    streaming_outline_data = {
                        "outlines": completed_outlines,  # All website outlines with traffic data
                        "generated_at": current_time,
                        "service_type": "streaming_advanced",
                        "primary_keyword": primary_keyword,
                        "subcategory": subcategory,
                        "country": country,
                        "total_websites": len(search_results),
                        "successful_outlines": len(completed_outlines),
                        "search_query": f"{subcategory} {primary_keyword}",
                        "websites_analyzed": [
                            {
                                "url": outline["url"],
                                "title": outline["title"], 
                                "traffic": outline["traffic"],
                                "outline_sections": len(outline["outline"].get("sections", [])) if isinstance(outline["outline"], dict) else 0
                            } for outline in completed_outlines
                        ]
                    }
                    
                    # Check if outlines.advanced exists, if not initialize it
                    blog_doc = mongodb_service.get_sync_db()['blogs'].find_one(
                        {"_id": ObjectId(blog_id)},
                        {"outlines": 1}
                    )
                    
                    if blog_doc:
                        outlinesuggestion_array = blog_doc.get("outlinesuggestion", [])
                        if not isinstance(outlinesuggestion_array, list):
                            # Initialize outlinesuggestion as empty array
                            mongodb_service.get_sync_db()['blogs'].update_one(
                                {"_id": ObjectId(blog_id)},
                                {"$set": {"outlinesuggestion": []}}
                            )
                        
                        # Save streaming outlines to MongoDB as outlinesuggestion
                        update_result = mongodb_service.get_sync_db()['blogs'].update_one(
                            {"_id": ObjectId(blog_id)},
                            {
                                "$push": {
                                    "outlinesuggestion": streaming_outline_data
                                },
                                "$set": {
                                    "updated_at": current_time
                                }
                            }
                        )
                        
                        logger.info(f"✅ Streaming outlines saved to outlinesuggestion - Modified: {update_result.modified_count}")
                        logger.info(f"📊 Saved {len(completed_outlines)} website outlines to blog {blog_id}")
                    
                except Exception as save_error:
                    logger.error(f"❌ Failed to save streaming outlines to MongoDB: {save_error}")
                    # Don't fail the entire process if saving fails
            
            # Final streaming completion event
            yield {
                "status": "complete",
                "message": f"Streaming outline generation complete! Analyzed {len(completed_outlines)} websites.",
                "data": {
                    "total_outlines": len(completed_outlines)
                }
            }
            
        except Exception as e:
            logger.error(f"Simple streaming error: {str(e)}")
            yield {
                "status": "error",
                "message": f"Error: {str(e)}"
            }

    async def _perform_search(self, primary_keyword: str, subcategory: str, country: str) -> List[Dict]:
        """🔍 SEARCH PIPELINE: Reliable Serper API search (like fast_async_scraper)"""
        search_query = f"{subcategory} {primary_keyword}"
        
        logger.info(f"🔍 SERPER SEARCH: {search_query} (country: {country})")
        
        try:
            # Use Serper API for reliable search (same as fast_async_scraper)
            search_start_time = datetime.now()
            
            # Serper API endpoint
            serper_url = "https://google.serper.dev/search"
            
            # Prepare request parameters
            params = {
                'q': search_query,
                'gl': country.lower() if country else 'us',
                'apiKey': settings.SERPER_API_KEY
            }
            
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': settings.SERPER_API_KEY
            }
            
            logger.info(f"🔗 SERPER API call for query: '{search_query}', country: {country}")
            
            async with self.http_session.get(
                serper_url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                response_time = (datetime.now() - search_start_time).total_seconds()
                logger.info(f"📈 Serper response in {response_time:.3f}s - Status: {response.status}")
                
                if response.status != 200:
                    logger.error(f" Serper API error: {response.status}")
                    error_content = await response.text()
                    logger.error(f"Error content: {error_content}")
                    raise Exception(f"Serper API returned status {response.status}")
                
                json_response = await response.json()
                logger.info(f"📄 Retrieved Serper JSON response")
                
                # Parse Serper API response format
                organic_results = json_response.get('organic', [])
                logger.info(f"🔄 Processing {len(organic_results)} Serper results...")
                
                # Format results (same structure as before)
                formatted_results = []
                for result in organic_results[:5]:  # Take first 5 results
                    formatted_results.append({
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "description": result.get("snippet", ""),
                        "traffic_data": None  # Will be filled later
                    })
                
                total_time = (datetime.now() - search_start_time).total_seconds()
                logger.info(f"✅ Serper search completed in {total_time:.3f}s - Found {len(formatted_results)} results")
                
                if not formatted_results:
                    logger.warning(f"⚠️ No search results found for query: '{search_query}'")
                
                return formatted_results
                
        except Exception as e:
            logger.error(f"💥 Serper search failed for '{search_query}': {str(e)}")
            # Fallback to empty results rather than crashing
            return []

    async def _get_traffic_data_parallel(self, search_results: List[Dict]) -> Dict[str, int]:
        """📊 SIMPLE TRAFFIC: Just hit SEMrush API for each URL"""
        traffic_data = {}
        
        if not self.semrush_api_key:
            logger.warning("📊 No SEMrush API key - skipping traffic data")
            return traffic_data
        
        logger.info(f"📊 Starting traffic data collection for {len(search_results)} URLs")
        
        # Simple: just call API for each URL
        for i, result in enumerate(search_results, 1):
            url = result["url"]
            logger.info(f"📊 [{i}/{len(search_results)}] Getting traffic for: {url[:60]}...")
            
            traffic = await self._fetch_single_url_traffic(url)
            traffic_data[url] = traffic
            result["traffic_data"] = traffic
            
            logger.info(f"📊 [{i}/{len(search_results)}] Traffic result: {traffic} for {url[:60]}...")
        
        logger.info(f"📊 Traffic collection complete. Total URLs processed: {len(search_results)}")
        return traffic_data


    
    async def _generate_single_outline(self, content: str) -> Dict:
        """🤖 Simple outline generation"""
        try:
            from app.prompts.blogGenerator.outline.outline_website import outline_website_prompt
            
            prompt = outline_website_prompt(content)
            
            # Call OpenAI API using the new responses.create format (same as meta_description_service)
            response = await self.openai_client.responses.create(
                model=settings.OPENAI_MODEL_MINI,
                input=[
                    {"role": "system", "content": "You are an expert content strategist and outline generator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Extract content using the same approach as meta_description_service
            outline_content = response.output_text.strip()
            logger.info(f"🤖 OpenAI outline response length: {len(outline_content)} chars")
            
            # Log usage to enhanced LLM service (same as meta_description_service)
            try:
                # Get model name and usage data
                model_name = getattr(response, 'model', settings.OPENAI_MODEL_MINI)
                usage_data = getattr(response, 'usage', None)
                
                if usage_data:
                    input_tokens = getattr(usage_data, 'input_tokens', 0)
                    output_tokens = getattr(usage_data, 'output_tokens', 0)
                    logger.info(f"🤖 Usage data - Input: {input_tokens}, Output: {output_tokens}")
                else:
                    # Fallback to estimated tokens
                    input_tokens = len(prompt) // 4
                    output_tokens = len(outline_content) // 4
                    logger.warning(f"🤖 No usage data, using estimates - Input: {input_tokens}, Output: {output_tokens}")
                
                # Record LLM usage with billing
                if hasattr(self, 'llm_usage_service') and self.llm_usage_service:
                    usage_metadata = {
                        "outline_generation": {
                            "content_length": len(content),
                            "model": model_name,
                            "service": "streaming_outline"
                        }
                    }
                    
                    self.llm_usage_service.record_llm_usage(
                        user_id=self.user_id,
                        service_name="outline_generation_streaming",
                        model_name=model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        service_description="Streaming outline generation using OpenAI",
                        project_id=self.project_id,
                        additional_metadata=usage_metadata
                    )
                    logger.info(f"✅ Usage logged successfully")
                
            except Exception as usage_error:
                logger.warning(f"⚠️ Failed to log usage (non-critical): {usage_error}")
            
            # Try to parse as JSON
            try:
                parsed_outline = json.loads(outline_content.strip())
                return parsed_outline
            except json.JSONDecodeError:
                # Return raw content if JSON parsing fails
                return {"raw_content": outline_content, "sections": [], "conclusion": "", "faqs": []}
                
        except Exception as e:
            logger.error(f"Outline generation failed: {e}")
            return {"error": str(e), "sections": [], "conclusion": "", "faqs": []}



    async def _scrape_single_website(self, url: str) -> str:
        """🕷️ Website scraping with RayoScraper and detailed logging"""
        scrape_start = datetime.now()
        logger.info(f"🚀 [OUTLINE-SCRAPE] Starting scraping for: {url}")
        logger.info(f"🕒 [OUTLINE-SCRAPE] Started at: {scrape_start.strftime('%H:%M:%S.%f')[:-3]}")
        
        try:
            # Try RayoScraper first if available
            if self.rayo_scraper and RAYO_SCRAPER_AVAILABLE:
                logger.info(f"🚀 [OUTLINE-SCRAPE] Using RayoScraper for: {url}")
                
                # Simple metadata with only comments
                additional_metadata = {
                    "comments": "Outline generation scraping"
                }
                
                rayo_result = await self.rayo_scraper.scrape_website(
                    url=url,
                    project_id=self.project_id,
                    blog_id=self.current_blog_id,
                    additional_metadata=additional_metadata
                )
                scrape_duration = (datetime.now() - scrape_start).total_seconds()
                
                if rayo_result.get("status") == "completed" and rayo_result.get("content"):
                    content = rayo_result["content"]
                    logger.info(f"✅ [OUTLINE-SCRAPE] RayoScraper SUCCESS in {scrape_duration:.3f}s")
                    logger.info(f"📊 [OUTLINE-SCRAPE] Content length: {len(content)} characters")
                    logger.info(f"🎯 [OUTLINE-SCRAPE] URL: {url[:60]}...")
                    return content
                else:
                    error_msg = rayo_result.get('error', 'Unknown error')
                    logger.error(f"❌ [OUTLINE-SCRAPE] RayoScraper failed: {error_msg}")
                    logger.error(f"🔗 [OUTLINE-SCRAPE] Failed URL: {url}")
                    return ""
            else:
                # Fallback to FastAsyncScraper if RayoScraper not available
                logger.warning(f"⚠️ [OUTLINE-SCRAPE] RayoScraper not available, using FastAsyncScraper")
                content = await self.fast_scraper.scrape_url(url)
                scrape_duration = (datetime.now() - scrape_start).total_seconds()
                logger.info(f"✅ [OUTLINE-SCRAPE] FastAsyncScraper completed in {scrape_duration:.3f}s")
                logger.info(f"📊 [OUTLINE-SCRAPE] Content length: {len(content)} characters")
                return content
                
        except Exception as e:
            scrape_duration = (datetime.now() - scrape_start).total_seconds()
            logger.error(f"❌ [OUTLINE-SCRAPE] Scraping failed after {scrape_duration:.3f}s")
            logger.error(f"💥 [OUTLINE-SCRAPE] Error: {str(e)}")
            logger.error(f"🔗 [OUTLINE-SCRAPE] Failed URL: {url}")
            logger.error(f"🔍 [OUTLINE-SCRAPE] Error type: {type(e).__name__}")
            return ""

    async def _fetch_single_url_traffic(self, url: str) -> int:
        """📊 SIMPLE: Get domain traffic from SEMrush (more reliable than URL-level)"""
        try:
            from urllib.parse import urlparse
            
            # Extract domain from URL for better success rate
            domain = urlparse(url).netloc
            
            params = {
                "key": self.semrush_api_key,
                "type": "domain_ranks",  # Changed from url_ranks to domain_ranks
                "export_columns": "Ot",
                "domain": domain,        # Changed from url to domain
                "database": "us"
            }
            
            logger.info(f"📊 SEMrush API call - URL: {url[:50]}... | Domain: {domain} | Params: {params}")
            
            async with self.http_session.get(self.semrush_api_url, params=params) as response:
                logger.info(f"📊 SEMrush Response - Status: {response.status} | URL: {url[:50]}...")
                
                if response.status == 200:
                    response_text = await response.text()
                    logger.info(f"📊 SEMrush Raw Response - Length: {len(response_text)} chars | First 100 chars: {response_text[:100]}")
                    
                    if response_text.startswith("ERROR"):
                        logger.warning(f"📊 SEMrush API Error - Response: {response_text} | URL: {url[:50]}...")
                        return 0
                    
                    lines = response_text.strip().split('\n')
                    logger.info(f"📊 SEMrush Response Lines - Total: {len(lines)} | Lines: {lines}")
                    
                    if len(lines) <= 1:
                        logger.warning(f"📊 SEMrush No Data - Only header line found | URL: {url[:50]}...")
                        return 0
                    
                    for line_num, line in enumerate(lines[1:], 1):
                        logger.info(f"📊 Processing Line {line_num} - Content: '{line.strip()}'")
                        if line.strip() and line.strip().isdigit():
                            traffic_value = int(line.strip())
                            logger.info(f"📊 SEMrush SUCCESS - Traffic: {traffic_value} | URL: {url[:50]}...")
                            return traffic_value
                    
                    logger.warning(f"📊 SEMrush No Valid Traffic - No numeric data found in response | URL: {url[:50]}...")
                    return 0
                else:
                    logger.error(f"📊 SEMrush HTTP Error - Status: {response.status} | URL: {url[:50]}...")
                    return 0
                    
        except Exception as e:
            logger.error(f"📊 SEMrush Exception - Error: {str(e)} | URL: {url[:50]}...")
            return 0

# _async_scrape_single_url method removed - not used by SSE endpoint

