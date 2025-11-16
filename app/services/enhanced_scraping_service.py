"""
Enhanced Scraping Service with MagicScraper Integration
Combines MagicScraper's advanced strategies with FastAsyncScraper fallback
"""

import asyncio
from typing import Dict, Any, Optional
from uuid import UUID
import logging
from app.services.mongodb_service import MongoDBService, MongoDBServiceError
from app.models.mongodb_models import ScrapedContent
from app.services.openai_service import OpenAIService
from app.db.session import get_db_session
from app.core.logging_config import logger
from app.core.config import settings

# Import RayoScraper
try:
    from app.services.rayo_scraper import RayoScrapingService
    RAYO_SCRAPER_AVAILABLE = True
    logger.info("✅ RayoScraper available for enhanced scraping")
except ImportError as e:
    RAYO_SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️ RayoScraper not available: {e}. Enhanced scraping will be disabled.")


class EnhancedScrapingService:
    """Enhanced scraping service with RayoScraper only"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.rayo_scraper = RayoScrapingService(user_id=user_id) if RAYO_SCRAPER_AVAILABLE else None
        
        logger.info(f"🚀 EnhancedScrapingService initialized - RayoScraper: {RAYO_SCRAPER_AVAILABLE}")
    
    async def scrape_website_enhanced(self, url: str) -> Dict[str, Any]:
        """Enhanced website scraping with RayoScraper primary + FastAsyncScraper fallback"""
        logger.info(f"🚀 [ENHANCED] Starting enhanced scraping workflow for URL: {url}")
        logger.info(f"👤 [ENHANCED] User ID: {self.user_id}")
        
        try:
            # URL validation
            if not url.startswith(('http://', 'https://')):
                error_msg = "Invalid URL format. URL must start with http:// or https://"
                logger.error(f"❌ [ENHANCED] URL validation failed: {error_msg}: {url}")
                return {
                    "status": "failed",
                    "current_stage": "scraping",
                    "error": error_msg,
                    "status_code": 400,
                    "error_type": "ValidationError"
                }

            logger.info(f"✅ [ENHANCED] URL validation passed for: {url}")
            
            # Try RayoScraper if available
            if RAYO_SCRAPER_AVAILABLE and self.rayo_scraper:
                logger.info(f"🚀 [ENHANCED] Attempting RayoScraper...")
                rayo_result = await self._try_rayo_scraper(url)
                
                if rayo_result["status"] == "completed":
                    logger.info(f"✅ [ENHANCED] RayoScraper succeeded for: {url}")
                    return rayo_result
                else:
                    error_msg = rayo_result.get('error', 'Unknown error')
                    logger.error(f"❌ [ENHANCED] RayoScraper failed: {error_msg}")
                    return {
                        "status": "failed",
                        "current_stage": "scraping",
                        "error": f"RayoScraper failed: {error_msg}",
                        "status_code": 500,
                        "error_type": "RayoScrapingError"
                    }
            else:
                # No RayoScraper available
                logger.error(f"❌ [ENHANCED] RayoScraper not available for: {url}")
                return {
                    "status": "failed",
                    "current_stage": "scraping", 
                    "error": "RayoScraper not available",
                    "status_code": 500,
                    "error_type": "ServiceUnavailableError"
                }
            
        except Exception as e:
            error_msg = f"Enhanced scraper failed: {str(e)}"
            logger.error(f"💥 [ENHANCED] Exception in scrape_website_enhanced:")
            logger.error(f"💥 [ENHANCED] Exception type: {type(e).__name__}")
            logger.error(f"💥 [ENHANCED] Exception message: {str(e)}")
            return {
                "status": "failed",
                "current_stage": "scraping",
                "error": error_msg,
                "status_code": 500,
                "error_type": "ScrapingError"
            }
    
    async def _try_rayo_scraper(self, url: str) -> Dict[str, Any]:
        """Try async RayoScraper with external API"""
        try:
            logger.info(f"🚀 [RAYO] Starting async RayoScraper for: {url}")
            
            # Use async RayoScraper method  
            result = await self.rayo_scraper.start_scraping_process(url, "temp-project-id")
            
            if result and result.get("status") == "completed":
                content = result.get("content", "")
                strategy_used = result.get("strategy_used", "unknown")
                
                logger.info(f"✅ [RAYO] Success with {strategy_used}")
                logger.info(f"📏 [RAYO] Content length: {len(content)}")
                
                # Validate content quality
                if len(content.strip()) < settings.MIN_CONTENT_LENGTH:
                    logger.error(f"📉 [RAYO] Content validation failed - length: {len(content)}")
                    raise Exception(f"Insufficient content retrieved: only {len(content)} characters")
                
                # Limit content size to prevent memory issues
                if len(content) > settings.MAX_CONTENT_LENGTH:
                    logger.warning(f"⚠️ [RAYO] Content too large ({len(content)} chars), truncating to {settings.MAX_CONTENT_LENGTH}")
                    content = content[:settings.MAX_CONTENT_LENGTH] + "... [Content truncated due to size]"
                
                return {
                    "status": "completed",
                    "current_stage": "scraping_completed",
                    "content": content.strip(),
                    "status_code": 200,
                    "scraper_metadata": {
                        "scraper_type": "RayoScraper",
                        "strategy_used": strategy_used,
                        "content_format": "markdown",
                        "original_title": "N/A"
                    }
                }
            else:
                raise Exception(f"RayoScraper failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"❌ [RAYO] RayoScraper error: {str(e)}")
            return {
                "status": "failed",
                "current_stage": "scraping",
                "error": f"RayoScraper failed: {str(e)}",
                "status_code": 500,
                "error_type": "RayoScrapingError"
            }
    
    
    def store_in_mongodb(self, scraping_result: Dict[str, Any], url: str, project_id: str) -> Dict[str, Any]:
        """Store the scraped content in MongoDB with enhanced metadata"""
        logger.info(f"💾 [ENHANCED] Starting MongoDB storage for URL: {url}")
        
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

            # Enhanced metadata from scraping result
            scraper_metadata = scraping_result.get("scraper_metadata", {})
            
            content = ScrapedContent(
                project_id=project_id,
                url=url,
                html_content=scraping_result["content"],
                status="completed",
                metadata={
                    "status_code": scraping_result.get("status_code", 200),
                    "content_length": len(scraping_result["content"]),
                    "scraper_type": scraper_metadata.get("scraper_type", "Unknown"),
                    "scraper_version": "enhanced_v1.0",
                    "strategy_used": scraper_metadata.get("strategy_used", "unknown"),
                    "content_format": scraper_metadata.get("content_format", "html"),
                    "original_title": scraper_metadata.get("original_title"),
                    "enhanced_scraping": True
                }
            )

            logger.info(f"💾 [ENHANCED] Attempting to save content to MongoDB")
            try:
                MongoDBService.save_scraped_content_sync(content)
                logger.info(f"✅ [ENHANCED] Successfully stored content in MongoDB for URL: {url}")

                return {
                    "status": "completed",
                    "current_stage": "storage_completed",
                    "message": "Content stored successfully in MongoDB with enhanced metadata",
                    "url": url,
                    "project_id": project_id,
                    "content": scraping_result["content"],
                    "scraper_metadata": scraper_metadata
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
        """Analyze services with enhanced content format awareness"""
        try:
            logger.info(f"🤖 [ENHANCED] Starting service analysis for URL: {url}")
            mongodb_service = MongoDBService()
            content = mongodb_service.get_content_by_url_sync(project_id=project_id, url=url)
            if not content:
                raise ValueError(f"Content not found for URL: {url}")

            text_content = content.html_content
            
            # Detect content format for better AI processing
            content_format = content.metadata.get("content_format", "html")
            scraper_type = content.metadata.get("scraper_type", "Unknown")
            
            logger.info(f"📄 [ENHANCED] Content format: {content_format}, Scraper: {scraper_type}")
            
            # Use async OpenAI processing
            analysis_result = await self._async_process_openai_analysis(url, text_content, project_id)

            if analysis_result["status"] != "success":
                logger.error(f"❌ [ENHANCED] OpenAI analysis failed: {analysis_result.get('error')}")
                return {
                    "status": "error",
                    "current_stage": "failed",
                    "error": analysis_result.get("error", "Analysis failed")
                }

            # Parse the OpenAI analysis response
            analysis_text = analysis_result["analysis"]
            
            try:
                import json
                import re
                
                # Extract JSON from code blocks
                json_pattern = r"```(?:json)?\n([\s\S]*?)\n```"
                match = re.search(json_pattern, analysis_text)
                if match:
                    analysis_data = json.loads(match.group(1).strip())
                else:
                    analysis_data = json.loads(analysis_text)
                    
                logger.info(f"🤖 [ENHANCED] Parsed OpenAI analysis: {analysis_data}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ [ENHANCED] Failed to parse OpenAI response: {str(e)}")
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
            
            logger.info(f"🤖 [ENHANCED] Extracted services: {services}")
            logger.info(f"🤖 [ENHANCED] Business category: {business_category}")

            # Update MongoDB content with enhanced analysis results
            content.services = services
            content.business_category = business_category
            content.ai_analysis_meta = {
                "service_analysis": {
                    "model": analysis_result["model"],
                    "tokens_used": analysis_result["tokens_used"],
                    "scraper_type": scraper_type,
                    "content_format": content_format,
                    "enhanced_processing": True
                }
            }

            MongoDBService.update_content(content)

            logger.info(f"✅ [ENHANCED] Service analysis completed for URL: {url}")
            return {
                "status": "completed",
                "current_stage": "completed",
                "project_id": project_id,
                "url": url,
                "services": services,
                "business_category": business_category,
                "scraper_metadata": storage_result.get("scraper_metadata", {})
            }

        except Exception as e:
            logger.error(f"❌ [ENHANCED] Service analysis failed: {str(e)}")
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
        with ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_SCRAPING) as executor:
            logger.info(f"🤖 [ENHANCED] Running OpenAI analysis in thread pool for {url}")
            result = await loop.run_in_executor(executor, sync_openai_analysis)
            logger.info(f"🤖 [ENHANCED] OpenAI analysis completed for {url}")
            return result
    
    async def start_scraping_process_enhanced(self, url: str, project_id: UUID) -> Dict[str, Any]:
        """Enhanced scraping workflow with MagicScraper + FastAsyncScraper"""
        project_id_str = str(project_id)
        
        logger.info(f"🚀 [ENHANCED] Starting FULL enhanced scraping workflow for URL: {url}")
        logger.info(f"🆔 [ENHANCED] Project ID: {project_id_str}")
        logger.info(f"👤 [ENHANCED] User ID: {self.user_id}")
        
        try:
            # Step 1: Enhanced website scraping
            logger.info(f"1️⃣ [ENHANCED] STEP 1: Starting enhanced website scraping...")
            scraping_result = await self.scrape_website_enhanced(url)
            logger.info(f"1️⃣ [ENHANCED] STEP 1 Result: {scraping_result.get('status')} - {scraping_result.get('error', 'Success')}")
            
            if scraping_result["status"] != "completed":
                logger.error(f"❌ [ENHANCED] Enhanced scraping failed for {url}")
                return {
                    "status": "failed",
                    "current_stage": "scraping",
                    "error": scraping_result.get("error", "Enhanced scraping failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            logger.info(f"✅ [ENHANCED] Enhanced scraping completed for {url}")

            # Step 2: Store in MongoDB with enhanced metadata
            logger.info(f"2️⃣ [ENHANCED] STEP 2: Starting MongoDB storage...")
            storage_result = self.store_in_mongodb(scraping_result, url, project_id_str)
            logger.info(f"2️⃣ [ENHANCED] STEP 2 Result: {storage_result.get('status')} - {storage_result.get('error', 'Success')}")
            
            if storage_result["status"] != "completed":
                logger.error(f"❌ [ENHANCED] Storage failed for {url}")
                return {
                    "status": "failed",
                    "current_stage": "storage", 
                    "error": storage_result.get("error", "Storage failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            logger.info(f"✅ [ENHANCED] Storage completed for {url}")

            # Step 3: Analyze services with enhanced context
            logger.info(f"3️⃣ [ENHANCED] STEP 3: Starting OpenAI service analysis...")
            analysis_result = await self.analyze_services(storage_result, project_id_str, url)
            if analysis_result["status"] != "completed":
                logger.error(f"❌ [ENHANCED] Analysis failed for {url}")
                return {
                    "status": "failed",
                    "current_stage": "analysis",
                    "error": analysis_result.get("error", "Analysis failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            logger.info(f"✅ [ENHANCED] Analysis completed for {url}")

            # Enhanced response with detailed metadata
            scraper_metadata = scraping_result.get("scraper_metadata", {})
            return {
                "status": "completed",
                "current_stage": "completed",
                "url": url,
                "project_id": project_id_str,
                "services": analysis_result.get("services", []),
                "business_category": analysis_result.get("business_category"),
                "scraper_type": scraper_metadata.get("scraper_type", "Enhanced"),
                "performance": "enhanced_optimized",
                "strategy_used": scraper_metadata.get("strategy_used", "unknown"),
                "content_format": scraper_metadata.get("content_format", "unknown")
            }

        except Exception as e:
            logger.error(f"❌ [ENHANCED] Process failed for {url}: {str(e)}")
            return {
                "status": "failed",
                "current_stage": "unknown",
                "error": str(e),
                "url": url,
                "project_id": project_id_str
            }


# Compatibility wrappers for easy migration
def create_enhanced_scraping_service(user_id: str) -> EnhancedScrapingService:
    """Create a new EnhancedScrapingService instance"""
    return EnhancedScrapingService(user_id)


class EnhancedScrapingServiceCompat:
    """Compatibility wrapper to use EnhancedScrapingService in place of FastScrapingServiceCompat"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.enhanced_service = EnhancedScrapingService(user_id)
    
    def start_scraping_process(self, url: str, project_id: UUID) -> Dict[str, Any]:
        """Synchronous wrapper for async enhanced scraping process"""
        try:
            # Run the async function
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.enhanced_service.start_scraping_process_enhanced(url, project_id))
                        return future.result()
                else:
                    return loop.run_until_complete(self.enhanced_service.start_scraping_process_enhanced(url, project_id))
            except RuntimeError:
                return asyncio.run(self.enhanced_service.start_scraping_process_enhanced(url, project_id))
        except Exception as e:
            logger.error(f"❌ Enhanced Scraper Compat: Failed to run async process: {str(e)}")
            return {
                "status": "failed",
                "current_stage": "compatibility_layer",
                "error": f"Enhanced async execution failed: {str(e)}",
                "url": url,
                "project_id": str(project_id)
            }


def create_enhanced_scraping_service_compat(user_id: str) -> EnhancedScrapingServiceCompat:
    """Create a compatibility wrapper for existing sync code"""
    return EnhancedScrapingServiceCompat(user_id)