from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import re
import json
from uuid import UUID
from datetime import datetime
import logging
from app.services.mongodb_service import MongoDBService, MongoDBServiceError
from app.models.mongodb_models import ScrapedContent
from app.services.openai_service import OpenAIService
from app.services.oxylabs_service import OxylabsService
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

class ScrapingService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def scrape_website(self, url: str) -> Dict[str, Any]:
        """Scrape website content and extract clean text."""
        logger.info(f"Starting scraping for URL: {url}")
        
        try:
            if not url.startswith(('http://', 'https://')):
                error_msg = "Invalid URL format. URL must start with http:// or https://"
                logger.error(f"{error_msg}: {url}")
                return {
                    "status": "failed",
                    "current_stage": "scraping",
                    "error": error_msg,
                    "status_code": 400,
                    "error_type": "ValidationError"
                }

            # Using Oxylabs service for scraping
            oxylabs_service = OxylabsService()
            # html_content = oxylabs_service.scrape_url(url)
            try:
                # Set a timeout for the entire scraping operation
                html_content = oxylabs_service.scrape_url_with_selenium(url)
                
                # Limit the size of HTML content to prevent HTTP protocol errors
                if len(html_content) > 500000:  # Limit to ~500KB
                    logger.warning(f"HTML content for {url} is too large ({len(html_content)} bytes), truncating")
                    html_content = html_content[:500000] + "... [Content truncated due to size]"
                
                print("-------------------\nHTML Content Length: " + str(len(html_content)) + " bytes\n-------------------")
                
            except Exception as scrape_error:
                logger.error(f"Error during Selenium scraping: {str(scrape_error)}")
                # Fall back to regular scraping
                html_content = oxylabs_service.scrape_url(url)
                
                # Limit the size of HTML content to prevent HTTP protocol errors
                if len(html_content) > 500000:  # Limit to ~500KB
                    logger.warning(f"HTML content for {url} is too large ({len(html_content)} bytes), truncating")
                    html_content = html_content[:500000] + "... [Content truncated due to size]"

            logger.info(f"Cleaning RAW HTML content from URL: {url}")
            # 🚀 REMOVED MARKDOWN CONVERSION: Keep raw HTML structure
            # Parse HTML with BeautifulSoup for cleaning
            soup = BeautifulSoup(html_content, 'html.parser')
            
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
            
            logger.info(f"Successfully scraped URL: {url} (RAW HTML content length: {len(cleaned_html)})")
            return {
                "status": "completed",
                "current_stage": "scraping_completed",
                "content": cleaned_html.strip(),
                "status_code": 200
            }

        except requests.RequestException as e:
            error_msg = f"HTTP Error occurred: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "current_stage": "scraping",
                "error": error_msg,
                "status_code": getattr(e, 'status', 500),
                "error_type": "HTTPError"
            }

        except Exception as e:
            error_msg = f"Unexpected error occurred: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "current_stage": "scraping",
                "error": error_msg,
                "status_code": 500,
                "error_type": "UnexpectedError"
            }

    def store_in_mongodb(self, scraping_result: Dict[str, Any], url: str, project_id: str) -> Dict[str, Any]:
        """Store the scraped content in MongoDB."""
        logger.info(f"Starting MongoDB storage for URL: {url}")
        
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
                    "content_length": len(scraping_result["content"])
                }
            )

            logger.info(f"Attempting to save content object to MongoDB")
            try:
                MongoDBService.save_scraped_content_sync(content)
                logger.info(f"Successfully stored content in MongoDB for URL: {url}")

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
                logger.exception("MongoDB error traceback:")
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
            logger.exception("Full traceback:")
            return {
                "status": "failed",
                "current_stage": "storage",
                "error": error_msg,
                "url": url,
                "project_id": project_id
            }

    def analyze_services(self, storage_result: Dict[str, Any], project_id: str, url: str) -> Dict[str, Any]:
        """Analyze the services offered by a website using OpenAI."""
        try:
            logger.info(f"Starting service analysis for URL: {url}")
            mongodb_service = MongoDBService()
            content = mongodb_service.get_content_by_url_sync(project_id=project_id, url=url)
            if not content:
                raise ValueError(f"Content not found for URL: {url}")

            text_content = content.html_content
            
            # Create OpenAI service with proper user_id and project_id
            with get_db_session() as db_session:
                openai_service = OpenAIService(db=db_session, user_id=self.user_id, project_id=project_id)
                analysis_result = openai_service.analyze_services(url=url, html_content=text_content)

            if analysis_result["status"] != "success":
                error_msg = analysis_result.get('error', 'Unknown error')
                raise ValueError("OpenAI analysis failed: " + str(error_msg))

            analysis_text = analysis_result["analysis"]

            try:
                json_pattern = r"```(?:json)?\n([\s\S]*?)\n```"
                match = re.search(json_pattern, analysis_text)
                if match:
                    analysis_data = json.loads(match.group(1).strip())
                else:
                    analysis_data = json.loads(analysis_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response: {str(e)}")
                logger.error(f"Raw response: {analysis_text}")
                raise ValueError("Invalid JSON response from OpenAI: " + str(e))

            services = analysis_data.get("products_services", [])
            if isinstance(services, str):
                services = [s.strip() for s in services.split(",")] if services else []
            business_category = analysis_data.get("business_category", "Others")

            content.services = services
            content.business_category = business_category
            content.ai_analysis_meta = {
                "service_analysis": {
                    "model": analysis_result["model"],
                    "tokens_used": analysis_result["tokens_used"]
                }
            }

            MongoDBService.update_content(content)

            return {
                "status": "completed",
                "current_stage": "completed",
                "project_id": project_id,
                "url": url,
                "services": services,
                "business_category": business_category
            }

        except Exception as e:
            logger.error(f"Service analysis failed: {str(e)}")
            logger.error(f"Full traceback:", exc_info=True)
            return {
                "status": "error",
                "current_stage": "failed",
                "error": str(e)
            }

    def start_scraping_process(self, url: str, project_id: UUID) -> Dict[str, Any]:
        """Start the scraping workflow for a given URL."""
        project_id_str = str(project_id)
        
        try:
            # Step 1: Scrape website
            scraping_result = self.scrape_website(url)
            if scraping_result["status"] != "completed":
                return {
                    "status": "failed",
                    "current_stage": "scraping",
                    "error": scraping_result.get("error", "Scraping failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            # Step 2: Store in MongoDB
            storage_result = self.store_in_mongodb(scraping_result, url, project_id_str)
            if storage_result["status"] != "completed":
                return {
                    "status": "failed",
                    "current_stage": "storage",
                    "error": storage_result.get("error", "Storage failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            # Step 3: Analyze services
            analysis_result = self.analyze_services(storage_result, project_id_str, url)
            if analysis_result["status"] != "completed":
                return {
                    "status": "failed",
                    "current_stage": "analysis",
                    "error": analysis_result.get("error", "Analysis failed"),
                    "url": url,
                    "project_id": project_id_str
                }

            return {
                "status": "completed",
                "current_stage": "completed",
                "url": url,
                "project_id": project_id_str,
                "services": analysis_result.get("services", []),
                "business_category": analysis_result.get("business_category")
            }

        except Exception as e:
            logger.error(f"Scraping process failed: {str(e)}")
            return {
                "status": "failed",
                "current_stage": "unknown",
                "error": str(e),
                "url": url,
                "project_id": project_id_str
            }
