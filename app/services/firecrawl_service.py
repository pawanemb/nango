from typing import Dict, List, Optional, Union
import httpx
from pydantic import BaseModel
from app.core.config import settings

class FirecrawlResponse(BaseModel):
    status: str
    url: str
    content: Dict[str, str]
    error: Optional[str] = None

class FirecrawlService:
    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY
        self.base_url = "https://api.firecrawl.dev/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def scrape_url(
        self, 
        url: str, 
        formats: List[str] = ["markdown", "html"],
        custom_params: Optional[Dict] = None
    ) -> FirecrawlResponse:
        """
        Scrape content from a URL in specified formats.
        
        Args:
            url: The URL to scrape
            formats: List of formats to return (markdown and/or html)
            custom_params: Additional parameters to pass to the Firecrawl API
            
        Returns:
            FirecrawlResponse object containing the scraped content
        """
        try:
            params = {
                "url": url,
                "formats": formats
            }
            
            if custom_params:
                params.update(custom_params)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/scrape",
                    headers=self.headers,
                    json=params
                )
                response.raise_for_status()
                data = response.json()
                
                return FirecrawlResponse(
                    status="success",
                    url=url,
                    content=data["content"]
                )

        except httpx.HTTPError as e:
            return FirecrawlResponse(
                status="error",
                url=url,
                content={},
                error=f"HTTP error occurred: {str(e)}"
            )
        except Exception as e:
            return FirecrawlResponse(
                status="error",
                url=url,
                content={},
                error=f"An error occurred: {str(e)}"
            )

