"""
🚀 Fast Scraping Service for Project Creation
Uses Enhanced Scraping Service with MagicScraper + FastAsyncScraper fallback
"""

import asyncio
from typing import Dict, Any
from uuid import UUID
import logging
from app.services.fast_async_scraper import create_fast_scraper
from app.services.mongodb_service import MongoDBService, MongoDBServiceError
from app.models.mongodb_models import ScrapedContent
from app.services.openai_service import OpenAIService
from app.db.session import get_db_session
from app.core.logging_config import logger
from app.core.config import settings

# Import Enhanced Scraping Service
try:
    from app.services.enhanced_scraping_service import EnhancedScrapingService
    ENHANCED_SCRAPING_AVAILABLE = True
    logger.info("✅ Enhanced Scraping Service available")
except ImportError as e:
    ENHANCED_SCRAPING_AVAILABLE = False
    logger.warning(f"⚠️ Enhanced Scraping Service not available: {e}. Using legacy FastAsyncScraper only.")


class FastScrapingService:
    """Fast scraping service with Enhanced Scraping + FastAsyncScraper fallback"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.fast_scraper = create_fast_scraper()
        
        # Enhanced scraping configuration
        self.use_enhanced_scraping = settings.USE_ENHANCED_SCRAPING
        
        # Initialize enhanced scraper if available
        if ENHANCED_SCRAPING_AVAILABLE and self.use_enhanced_scraping:
            self.enhanced_scraper = EnhancedScrapingService(user_id)
            logger.info(f"🚀 FastScrapingService initialized with Enhanced Scraping enabled")
        else:
            self.enhanced_scraper = None
            logger.info(f"🚀 FastScrapingService initialized with legacy FastAsyncScraper only")
    
    async def scrape_website_fast(self, url: str) -> Dict[str, Any]:
        """Fast website scraping using FastAsyncScraper"""
        logger.info(f"🚀 [DEBUG] FastScraper: Starting scraping workflow for URL: {url}")
        logger.info(f"👤 [DEBUG] User ID: {self.user_id}")
        
        try:
            if not url.startswith(('http://', 'https://')):
                error_msg = "Invalid URL format. URL must start with http:// or https://"
                logger.error(f"❌ [DEBUG] URL validation failed: {error_msg}: {url}")
                return {
                    "status": "failed",
                    "current_stage": "scraping",
                    "error": error_msg,
                    "status_code": 400,
                    "error_type": "ValidationError"
                }

            logger.info(f"✅ [DEBUG] URL validation passed for: {url}")
            # Use FastAsyncScraper for optimal performance
            logger.info(f"🔄 [DEBUG] Calling FastAsyncScraper.scrape_url...")
            try:
                # Use longer timeout for known problematic domains
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
                problematic_domains = ['fedex.com', 'ups.com', 'dhl.com', 'tnt.com']
                timeout = 25 if any(prob_domain in domain for prob_domain in problematic_domains) else 15
                
                logger.info(f"⏱️ [DEBUG] Using timeout: {timeout}s for domain: {domain}")
                content = await self.fast_scraper.scrape_url(url, timeout=timeout)
                logger.info(f"📥 [DEBUG] FastAsyncScraper returned content of length: {len(content) if content else 0}")
            except Exception as scrape_error:
                logger.error(f"🚨 [DEBUG] Direct scraping error: {str(scrape_error)}")
                logger.error(f"🚨 [DEBUG] Error type: {type(scrape_error).__name__}")
                raise scrape_error
            
            if not content or len(content.strip()) < 100:
                logger.error(f"📉 [DEBUG] Content validation failed - length: {len(content) if content else 0}")
                logger.error(f"💾 [DEBUG] Content preview: {content[:200] if content else 'None'}")
                raise Exception(f"Insufficient content retrieved: only {len(content)} characters")
            
            logger.info(f"✅ [DEBUG] Content validation passed - length: {len(content)}")
            
            # Limit content size to prevent memory issues
            if len(content) > 500000:  # Limit to ~500KB
                logger.warning(f"⚠️ [DEBUG] Content for {url} is too large ({len(content)} chars), truncating to 500KB")
                content = content[:500000] + "... [Content truncated due to size]"
            
            logger.info(f"✅ [DEBUG] FastScraper: Successfully scraped URL: {url} (final content length: {len(content)})")
            return {
                "status": "completed",
                "current_stage": "scraping_completed",
                "content": content.strip(),
                "status_code": 200
            }

        except Exception as e:
            error_msg = f"FastScraper failed: {str(e)}"
            logger.error(f"💥 [DEBUG] Exception in scrape_website_fast:")
            logger.error(f"💥 [DEBUG] Exception type: {type(e).__name__}")
            logger.error(f"💥 [DEBUG] Exception message: {str(e)}")
            logger.error(error_msg)
            return {
                "status": "failed",
                "current_stage": "scraping",
                "error": error_msg,
                "status_code": 500,
                "error_type": "ScrapingError"
            }
    
    def store_in_mongodb(self, scraping_result: Dict[str, Any], url: str, project_id: str) -> Dict[str, Any]:
        """Store the scraped content in MongoDB"""
        logger.info(f"💾 FastScraper: Starting MongoDB storage for URL: {url}")
        
        try:
            if scraping_result.get("status") != "completed":
                error_msg = f"Scraping failed: {scraping_result.get('error', 'Unknown error')}"
                logger.error(error_msg)
                return {
                    "status": "failed",
                    "current_stage": "storage",
                    "error": error_msg,
                    "url": url,
                    "project_id": project_id
                }

            content = ScrapedContent(
                project_id=project_id,
                url=url,
                html_content=scraping_result["content"],
                status="completed",
                metadata={
                    "status_code": scraping_result.get("status_code", 200),
                    "content_length": len(scraping_result["content"]),
                    "scraper_type": "FastAsyncScraper",
                    "scraper_version": "v1.0"
                }
            )

            logger.info(f"💾 FastScraper: Attempting to save content to MongoDB")
            try:
                MongoDBService.save_scraped_content_sync(content)
                logger.info(f"✅ FastScraper: Successfully stored content in MongoDB for URL: {url}")

                return {
                    "status": "completed",
                    "current_stage": "storage_completed",
                    "message": "Content stored successfully in MongoDB",
                    "url": url,
                    "project_id": project_id,
                    "content": scraping_result["content"]
                }
            except MongoDBServiceError as e:
                error_msg = f"MongoDB error: {str(e)}"
                logger.error(error_msg)
                return {
                    "status": "failed",
                    "current_stage": "storage",
                    "error": error_msg,
                    "url": url,
                    "project_id": project_id
                }

        except Exception as e:
            error_msg = f"Failed to prepare content for MongoDB storage: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "current_stage": "storage",
                "error": error_msg,
                "url": url,
                "project_id": project_id
            }
    
    async def analyze_services(self, storage_result: Dict[str, Any], project_id: str, url: str) -> Dict[str, Any]:
        """Analyze the services offered by a website using OpenAI - ASYNC VERSION"""
        try:
            logger.info(f"🤖 FastScraper: Starting ASYNC service analysis for URL: {url}")
            mongodb_service = MongoDBService()
            content = mongodb_service.get_content_by_url_sync(project_id=project_id, url=url)
            if not content:
                raise ValueError(f"Content not found for URL: {url}")

            text_content = content.html_content
            
            # Use async OpenAI processing with ThreadPoolExecutor
            analysis_result = await self._async_process_openai_analysis(url, text_content, project_id)

            if analysis_result["status"] != "success":
                logger.error(f"❌ FastScraper: OpenAI analysis failed: {analysis_result.get('error')}")
                return {
                    "status": "error",
                    "current_stage": "failed",
                    "error": analysis_result.get("error", "Analysis failed")
                }

            # Parse the OpenAI analysis response (JSON format)
            analysis_text = analysis_result["analysis"]
            
            try:
                import json
                import re
                
                # Try to extract JSON from code blocks first
                json_pattern = r"```(?:json)?\n([\s\S]*?)\n```"
                match = re.search(json_pattern, analysis_text)
                if match:
                    analysis_data = json.loads(match.group(1).strip())
                else:
                    # Try to parse the entire response as JSON
                    analysis_data = json.loads(analysis_text)
                    
                logger.info(f"🤖 FastScraper: Parsed OpenAI analysis: {analysis_data}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ FastScraper: Failed to parse OpenAI response: {str(e)}")
                logger.error(f"❌ FastScraper: Raw response: {analysis_text}")
                return {
                    "status": "error",
                    "current_stage": "failed",
                    "error": f"Invalid JSON response from OpenAI: {str(e)}"
                }

            # Extract services and business category
            services = analysis_data.get("products_services", [])
            if isinstance(services, str):
                services = [s.strip() for s in services.split(",")] if services else []
            business_category = analysis_data.get("business_category", "Others")
            
            logger.info(f"🤖 FastScraper: Extracted services: {services}")
            logger.info(f"🤖 FastScraper: Business category: {business_category}")

            # Update MongoDB content with analysis results
            content.services = services
            content.business_category = business_category
            content.ai_analysis_meta = {
                "service_analysis": {
                    "model": analysis_result["model"],
                    "tokens_used": analysis_result["tokens_used"],
                    "scraper_type": "FastAsyncScraper"
                }
            }

            MongoDBService.update_content(content)

            logger.info(f"✅ FastScraper: Service analysis completed for URL: {url}")
            return {
                "status": "completed",
                "current_stage": "completed",
                "project_id": project_id,
                "url": url,
                "services": services,
                "business_category": business_category
            }

        except Exception as e:
            logger.error(f"❌ FastScraper: Service analysis failed: {str(e)}")
            return {
                "status": "error",
                "current_stage": "failed",
                "error": str(e)
            }
    
    async def _async_process_openai_analysis(self, url: str, html_content: str, project_id: str) -> Dict[str, Any]:
        """Async OpenAI service analysis using ThreadPoolExecutor"""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        def sync_openai_analysis():
            """Synchronous OpenAI analysis to run in thread pool"""
            with get_db_session() as db_session:
                openai_service = OpenAIService(db=db_session, user_id=self.user_id, project_id=project_id)
                return openai_service.analyze_services(url=url, html_content=html_content)
        
        # Run OpenAI analysis in thread pool for non-blocking execution
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=5) as executor:
            logger.info(f"🤖 FastScraper: Running OpenAI analysis in thread pool for {url}")
            result = await loop.run_in_executor(executor, sync_openai_analysis)
            logger.info(f"🤖 FastScraper: OpenAI analysis completed for {url}")
            return result
    
    async def start_scraping_process_fast(self, url: str, project_id: UUID) -> Dict[str, Any]:
        """Fast scraping workflow with Enhanced Scraping + FastAsyncScraper fallback"""
        project_id_str = str(project_id)
        
        logger.info(f"🚀 [DEBUG] FastScraper: Starting FULL scraping workflow for URL: {url}")
        logger.info(f"🆔 [DEBUG] Project ID: {project_id_str}")
        logger.info(f"👤 [DEBUG] User ID: {self.user_id}")
        
        # Try Enhanced Scraping first if available
        if self.enhanced_scraper:
            logger.info(f"🪄 [DEBUG] Using Enhanced Scraping Service (MagicScraper + FastAsyncScraper)")
            try:
                result = await self.enhanced_scraper.start_scraping_process_enhanced(url, project_id)
                if result["status"] == "completed":
                    logger.info(f"✅ [DEBUG] Enhanced Scraping succeeded for {url}")
                    return result
                else:
                    logger.warning(f"⚠️ [DEBUG] Enhanced Scraping failed: {result.get('error')}")
            except Exception as enhanced_error:
                logger.error(f"❌ [DEBUG] Enhanced Scraping exception: {str(enhanced_error)}")
        
        # Fallback to legacy FastAsyncScraper workflow
        logger.info(f"🔄 [DEBUG] Falling back to legacy FastAsyncScraper workflow")
        
        try:
            # Step 1: Fast website scraping
            logger.info(f"1️⃣ [DEBUG] STEP 1: Starting website scraping...")
            scraping_result = await self.scrape_website_fast(url)
            logger.info(f"1️⃣ [DEBUG] STEP 1 Result: {scraping_result.get('status')} - {scraping_result.get('error', 'Success')}")
            
            if scraping_result["status"] != "completed":
                logger.error(f"❌ [DEBUG] FastScraper: Scraping failed for {url}")
                return {
                    "status": "failed",
                    "current_stage": "scraping",
                    "error": scraping_result.get("error", "Scraping failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            logger.info(f"✅ [DEBUG] FastScraper: Scraping completed for {url}")

            # Step 2: Store in MongoDB
            logger.info(f"2️⃣ [DEBUG] STEP 2: Starting MongoDB storage...")
            storage_result = self.store_in_mongodb(scraping_result, url, project_id_str)
            logger.info(f"2️⃣ [DEBUG] STEP 2 Result: {storage_result.get('status')} - {storage_result.get('error', 'Success')}")
            
            if storage_result["status"] != "completed":
                logger.error(f"❌ [DEBUG] FastScraper: Storage failed for {url}")
                return {
                    "status": "failed",
                    "current_stage": "storage", 
                    "error": storage_result.get("error", "Storage failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            logger.info(f"✅ [DEBUG] FastScraper: Storage completed for {url}")

            # Step 3: Analyze services (ASYNC)
            logger.info(f"3️⃣ [DEBUG] STEP 3: Starting OpenAI service analysis...")
            analysis_result = await self.analyze_services(storage_result, project_id_str, url)
            if analysis_result["status"] != "completed":
                logger.error(f"❌ FastScraper: Analysis failed for {url}")
                return {
                    "status": "failed",
                    "current_stage": "analysis",
                    "error": analysis_result.get("error", "Analysis failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            logger.info(f"✅ FastScraper: Analysis completed for {url}")

            return {
                "status": "completed",
                "current_stage": "completed",
                "url": url,
                "project_id": project_id_str,
                "services": analysis_result.get("services", []),
                "business_category": analysis_result.get("business_category"),
                "scraper_type": "FastAsyncScraper",
                "performance": "optimized"
            }

        except Exception as e:
            logger.error(f"❌ FastScraper: Process failed for {url}: {str(e)}")
            return {
                "status": "failed",
                "current_stage": "unknown",
                "error": str(e),
                "url": url,
                "project_id": project_id_str
            }


# Compatibility wrapper for easy migration
class FastScrapingServiceCompat:
    """Compatibility wrapper to use FastScrapingService in place of ScrapingService"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.fast_service = FastScrapingService(user_id)
    
    def start_scraping_process(self, url: str, project_id: UUID) -> Dict[str, Any]:
        """Synchronous wrapper for async fast scraping process"""
        try:
            # Run the async function in the current event loop or create a new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we need to create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.fast_service.start_scraping_process_fast(url, project_id))
                        return future.result()
                else:
                    return loop.run_until_complete(self.fast_service.start_scraping_process_fast(url, project_id))
            except RuntimeError:
                # No event loop exists, create a new one
                return asyncio.run(self.fast_service.start_scraping_process_fast(url, project_id))
        except Exception as e:
            logger.error(f"❌ FastScraper Compat: Failed to run async process: {str(e)}")
            return {
                "status": "failed",
                "current_stage": "compatibility_layer",
                "error": f"Async execution failed: {str(e)}",
                "url": url,
                "project_id": str(project_id)
            }


# Factory functions for easy usage
def create_fast_scraping_service(user_id: str) -> FastScrapingService:
    """Create a new FastScrapingService instance"""
    return FastScrapingService(user_id)

def create_fast_scraping_service_compat(user_id: str) -> FastScrapingServiceCompat:
    """Create a compatibility wrapper for existing sync code"""
    return FastScrapingServiceCompat(user_id)