import os
import aiohttp
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("fastapi_app")

class RayoScrapingService:
    """
    RayoScraper service for scraping websites using external Rayo scraper API.
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.base_url = "https://scraper.rayo.work"
        self.auth_token = os.getenv("RAYO_SCRAPER_TOKEN")
        self.timeout = 60
    
    async def start_scraping_process(self, url: str, project_id: str = None, blog_id: str = None, additional_metadata: Dict = None) -> Dict[str, Any]:
        """
        Start the async scraping process for a given URL and project.
        
        Args:
            url: The URL to scrape
            project_id: The project ID associated with this scraping task
            
        Returns:
            Dict containing scraping results
        """
        try:
            # Enhanced payload with tracking IDs and metadata
            payload = {
                "url": url,
                "output_format": "markdown",
                "user_id": self.user_id,
                "project_id": project_id,
                "blog_id": blog_id
            }
            
            # Add additional metadata if provided
            if additional_metadata:
                payload.update(additional_metadata)
            
            # Remove None values to keep payload clean
            payload = {k: v for k, v in payload.items() if v is not None}
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.auth_token}"
            }
            
            logger.info(f"🚀 RayoScraper API Call: {self.base_url}/scrape")
            logger.info(f"📋 Payload: {payload}")
            logger.info(f"🔑 Auth Token: {self.auth_token[:10]}..." if self.auth_token else "❌ No auth token")
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}/scrape",
                    json=payload,
                    headers=headers
                ) as response:
                    
                    if response.status != 200:
                        # Get detailed error response
                        try:
                            error_body = await response.text()
                            logger.error(f"🚨 RayoScraper API Error {response.status}: {error_body}")
                        except:
                            error_body = "Could not read error response"
                        
                        return {
                            "status": "failed",
                            "error": f"API request failed with status {response.status}: {error_body}",
                            "scraper_type": "RayoScraper"
                        }
                    
                    api_response = await response.json()
            
            if not api_response.get("success", False):
                return {
                    "status": "failed",
                    "error": "Scraping failed according to API response",
                    "scraper_type": "RayoScraper"
                }
            
            markdown_content = api_response.get("markdown", "")
            scrape_method = api_response.get("method", "unknown")
            
            return {
                "status": "completed",
                "services": [],
                "business_category": "Unknown",
                "scraper_type": "RayoScraper",
                "content_format": "markdown",
                "strategy_used": scrape_method,
                "content": markdown_content
            }
                
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Scraping process failed: {str(e)}",
                "scraper_type": "RayoScraper"
            }

    async def scrape_website(self, url: str, project_id: str = None, blog_id: str = None, additional_metadata: Dict = None) -> Dict[str, Any]:
        """
        Async method for website scraping (compatible with FastAsyncScraper).
        
        Args:
            url: The URL to scrape
            project_id: Optional project ID for tracking
            blog_id: Optional blog ID for tracking
            additional_metadata: Optional additional tracking data
            
        Returns:
            Dict containing scraping results
        """
        return await self.start_scraping_process(url, project_id, blog_id, additional_metadata)

def create_rayo_scraper_compat(user_id: str) -> RayoScrapingService:
    """
    Create a RayoScrapingService instance.
    """
    return RayoScrapingService(user_id=user_id)