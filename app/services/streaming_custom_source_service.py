"""
🚀 Streaming Custom Source Service
Real-time custom source processing with streaming updates
"""

from typing import AsyncGenerator, Dict, Any, Optional
from app.core.logging_config import logger
from app.db.session import get_db_session
from app.services.custom_source_prompts import CustomSourcePrompts
from datetime import datetime
import asyncio
import json
import aiohttp
import requests
from sqlalchemy.orm import Session


class StreamingCustomSourceService:
    """Service for streaming custom source processing with real-time updates"""
    
    def __init__(self, db: Session, user_id: str, project_id: str):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.prompts = CustomSourcePrompts()
        self._session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
    
    async def stream_custom_source_processing(
        self,
        outline_json: list,  # Changed to list to match frontend format
        subsection_data: dict,
        source_type: str,
        content: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        🚀 MAIN STREAMING METHOD: Process custom source with real-time updates
        """
        try:
            # Stage 1: Get content (text directly or scrape URL)
            processed_content = ""
            scraped_info = {}
            
            if source_type == "text":
                processed_content = content
                
            elif source_type == "url":
                yield {
                    "stage": "scraping",
                    "status": "processing",
                    "message": f"🔗 Scraping URL content...",
                    "timestamp": datetime.utcnow().isoformat(),
                    "debug": {
                        "target_url": content,
                        "step": "Starting HTTP request"
                    }
                }
                
                # Scrape URL content
                scrape_result = await self._scrape_url_content(content)
                if not scrape_result["success"]:
                    yield {
                        "stage": "scraping",
                        "status": "failed",
                        "message": f"❌ Failed to scrape URL: {scrape_result['error']}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "debug": {
                            "error": scrape_result['error'],
                            "url": content,
                            "step": "HTTP request failed"
                        }
                    }
                    return
                
                processed_content = scrape_result["content"]
                scraped_info = scrape_result["info"]
                
                yield {
                    "stage": "scraping",
                    "status": "completed",
                    "message": f"✅ Scraped {len(processed_content)} characters",
                    "scraped_content": processed_content[:500],  # Preview of scraped content
                    "timestamp": datetime.utcnow().isoformat(),
                    "debug": {
                        "http_status": scraped_info.get("status_code", "unknown"),
                        "content_length": len(processed_content),
                        "extracted_title": scraped_info.get("title", "unknown"),
                        "url": content,
                        "step": "HTML to text conversion completed"
                    }
                }
            
            # Generate title based on source type
            if source_type == "url":
                title = self._extract_title_from_html(scraped_info.get("original_html", "")) if scraped_info else "Website Source"
            else:
                title = "Text Source"

            # Process with OpenAI without streaming
            ai_result = await self._process_with_openai(
                outline_json=outline_json,
                subsection_data=subsection_data,
                content=processed_content,
                source_title=title,
                source_type=source_type,
                source_url=content if source_type == "url" else ""
            )
            
            if not ai_result["success"]:
                yield {
                    "stage": "ai_processing",
                    "status": "failed",
                    "message": f"❌ AI processing failed: {ai_result['error']}",
                    "timestamp": datetime.utcnow().isoformat(),
                    "debug": {
                        "ai_error": ai_result['error'],
                        "model_used": ai_result.get("model_used", "unknown"),
                        "processing_time": ai_result.get("processing_time", 0),
                        "step": "OpenAI API call failed"
                    }
                }
                return
            
            # Final completion
            yield {
                "stage": "complete",
                "status": "success",
                "results": ai_result.get("sources", {}),
                "timestamp": datetime.utcnow().isoformat(),
                "debug": {
                    "ai_model": ai_result.get("model_used", "gpt-4.1-2025-04-14"),
                    "processing_time": ai_result.get("processing_time", 0),
                    "raw_ai_response": ai_result.get("raw_response", "")[:1000],
                    "content_length_sent": len(processed_content),
                    "source_title": title,
                    "step": "Processing completed successfully"
                }
            }
            
        except Exception as e:
            logger.error(f"Streaming custom source processing failed: {str(e)}")
            yield {
                "stage": "error",
                "status": "failed",
                "message": f"❌ Processing failed: {str(e)}",
                "progress": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _scrape_url_content(self, url: str) -> Dict[str, Any]:
        """
        Scrape content from URL using Oxylabs or similar service
        """
        try:
            logger.info(f"🔗 STARTING URL SCRAPING:")
            logger.info(f"🎯 Target URL: {url}")
            # For demo purposes, using basic scraping
            # In production, you'd use Oxylabs or similar proxy service
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            if not self._session:
                self._session = aiohttp.ClientSession()
            
            logger.info(f"📡 Making HTTP request with User-Agent: {headers['User-Agent'][:50]}...")
            
            async with self._session.get(url, headers=headers, timeout=30) as response:
                logger.info(f"📊 HTTP Response: Status {response.status}")
                
                if response.status == 200:
                    html_content = await response.text()
                    logger.info(f"📥 Raw HTML received: {len(html_content)} characters")
                    logger.info(f"🔤 HTML Preview: {html_content[:300]}...")
                    
                    # Convert HTML to clean text using html2text
                    text_content = self._html_to_text(html_content)
                    title = self._extract_title_from_html(html_content)
                    
                    logger.info(f"✅ HTML to text conversion complete:")
                    logger.info(f"📄 Extracted Title: {title}")
                    logger.info(f"📏 Converted Text Length: {len(text_content)} characters")
                    logger.info(f"📝 Text Preview: {text_content[:500]}...")
                    
                    return {
                        "success": True,
                        "content": text_content,  # Full converted text
                        "info": {
                            "status_code": response.status,
                            "content_length": len(text_content),
                            "url": url,
                            "title": title,
                            "original_html": html_content
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: Unable to access URL",
                        "content": "",
                        "info": {}
                    }
                    
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timeout - URL took too long to respond",
                "content": "",
                "info": {}
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Scraping failed: {str(e)}",
                "content": "",
                "info": {}
            }
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML to clean readable text using html2text"""
        try:
            import html2text
            
            # Configure html2text
            h = html2text.HTML2Text()
            h.ignore_links = False  # Keep links as markdown
            h.ignore_images = True  # Remove images
            h.ignore_emphasis = False  # Keep bold/italic
            h.body_width = 0  # Don't wrap lines
            h.unicode_snob = True  # Use unicode
            
            # Convert HTML to markdown-style text
            text_content = h.handle(html_content)
            
            # Clean up extra whitespace
            import re
            text_content = re.sub(r'\n\s*\n\s*\n', '\n\n', text_content)  # Remove extra blank lines
            text_content = text_content.strip()
            
            return text_content
            
        except ImportError:
            # Fallback to basic regex if html2text not available
            logger.warning("html2text not available, using basic HTML stripping")
            import re
            # Remove script and style elements
            html_content = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL)
            html_content = re.sub(r'<style.*?</style>', '', html_content, flags=re.DOTALL)
            # Remove HTML tags
            text_content = re.sub(r'<[^>]+>', '', html_content)
            # Clean up whitespace
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            return text_content
    
    def _extract_title_from_html(self, html_content: str) -> str:
        """Extract title from HTML content"""
        import re
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        return "Untitled"
    
    def _clean_openai_response(self, response_text: str) -> str:
        """Clean OpenAI response by removing code blocks and extra formatting"""
        import re
        
        # Remove code block markers (```json, ```, etc.)
        cleaned = re.sub(r'```json\s*', '', response_text, flags=re.IGNORECASE)
        cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'```', '', cleaned)
        
        # Remove any leading/trailing whitespace
        cleaned = cleaned.strip()
        
        # If response starts with explanation text, try to extract just the JSON part
        # Look for the first { and last } to extract JSON
        json_start = cleaned.find('{')
        if json_start != -1:
            json_end = cleaned.rfind('}')
            if json_end != -1 and json_end > json_start:
                cleaned = cleaned[json_start:json_end+1]
        
        return cleaned
    
    async def _save_payload_to_file(self, prompt: dict, source_type: str, content: str, source_title: str, source_url: str = ""):
        """Save complete API payload to text file for debugging"""
        try:
            import os
            from datetime import datetime
            
            # Create debug directory if it doesn't exist
            debug_dir = "/tmp/openai_payloads"  # Use /tmp for temporary files
            os.makedirs(debug_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{debug_dir}/payload_{source_type}_{timestamp}.txt"
            
            # Prepare payload content
            payload_content = f"""
================================================================================
OPENAI API PAYLOAD DEBUG FILE
================================================================================
Generated: {datetime.now().isoformat()}
Source Type: {source_type}
Source Title: {source_title}
Source URL: {source_url if source_type == 'url' else 'N/A'}

================================================================================
SYSTEM PROMPT ({len(prompt['system'])} characters):
================================================================================
{prompt['system']}

================================================================================
USER PROMPT ({len(prompt['user'])} characters):
================================================================================
{prompt['user']}

================================================================================
CONTENT BEING PROCESSED ({len(content)} characters):
================================================================================
{content}

================================================================================
API PARAMETERS:
================================================================================
Model: gpt-4.1
Temperature: 1.0
Max Tokens: 16384
Stream: False

================================================================================
END OF PAYLOAD
================================================================================
"""
            
            # Write to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(payload_content)
            
            logger.info(f"💾 Payload saved to file: {filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save payload to file: {str(e)}")
    
    async def _save_response_to_file(self, raw_response: str, cleaned_response: str, source_type: str, source_title: str):
        """Save OpenAI response to text file for debugging"""
        try:
            import os
            from datetime import datetime
            
            # Create debug directory if it doesn't exist
            debug_dir = "/tmp/openai_payloads"
            os.makedirs(debug_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{debug_dir}/response_{source_type}_{timestamp}.txt"
            
            # Prepare response content
            response_content = f"""
================================================================================
OPENAI API RESPONSE DEBUG FILE
================================================================================
Generated: {datetime.now().isoformat()}
Source Type: {source_type}
Source Title: {source_title}

================================================================================
RAW RESPONSE ({len(raw_response)} characters):
================================================================================
{raw_response}

================================================================================
CLEANED RESPONSE ({len(cleaned_response)} characters):
================================================================================
{cleaned_response}

================================================================================
RESPONSE ANALYSIS:
================================================================================
Raw Response Length: {len(raw_response)}
Cleaned Response Length: {len(cleaned_response)}
Contains Code Blocks: {'```' in raw_response}
Starts with JSON: {cleaned_response.strip().startswith('{')}
Ends with JSON: {cleaned_response.strip().endswith('}')}

================================================================================
END OF RESPONSE
================================================================================
"""
            
            # Write to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(response_content)
            
            logger.info(f"📄 Response saved to file: {filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save response to file: {str(e)}")
    
    async def _process_with_openai(
        self,
        outline_json: list,  # Changed to list to match frontend format
        subsection_data: dict,
        content: str,
        source_title: str,
        source_type: str,
        source_url: str = ""
    ) -> Dict[str, Any]:
        """
        Process content with OpenAI without streaming - get complete response
        """
        try:
            start_time = datetime.utcnow()
            
            # Get the appropriate prompt based on source type
            if source_type == "url":
                prompt = self.prompts.get_url_source_prompt(
                    outline_json=outline_json,
                    subsection_data=subsection_data,
                    content=content,
                    source_title=source_title,
                    source_url=source_url
                )
                logger.info(f"🔗 URL SOURCE - OpenAI Payload:")
                logger.info(f"📤 SYSTEM PROMPT: {prompt['system'][:500]}...")
                logger.info(f"📤 USER PROMPT: {prompt['user'][:1000]}...")
                logger.info(f"📏 Content Length: {len(content)} characters")
                logger.info(f"🌐 URL: {source_url}")
                logger.info(f"📄 Title: {source_title}")
                
            else:  # text
                prompt = self.prompts.get_text_source_prompt(
                    outline_json=outline_json,
                    subsection_data=subsection_data,
                    content=content,
                    source_title=source_title
                )
                logger.info(f"📝 TEXT SOURCE - OpenAI Payload:")
                logger.info(f"📤 SYSTEM PROMPT: {prompt['system'][:500]}...")
                logger.info(f"📤 USER PROMPT: {prompt['user'][:1000]}...")
                logger.info(f"📏 Content Length: {len(content)} characters")
                logger.info(f"📄 Title: {source_title}")
            
            # Log complete OpenAI request details
            logger.info(f"🚀 SENDING TO OPENAI:")
            logger.info(f"🤖 Model: gpt-4.1")
            logger.info(f"🌡️ Temperature: 1.0")
            logger.info(f"🔢 Max Tokens: 16384")
            logger.info(f"📊 Stream: False")
            logger.info(f"💬 Messages Structure:")
            logger.info(f"   System Message Length: {len(prompt['system'])} chars")
            logger.info(f"   User Message Length: {len(prompt['user'])} chars")
            
            # Save complete payload to text file for debugging
            await self._save_payload_to_file(prompt, source_type, content, source_title, source_url)
            
            # Make OpenAI API call without streaming
            import openai
            from app.core.config import settings
            
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Get complete response without streaming
            response = await client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]}
                ],
                temperature=1.0,
                max_tokens=16384
            )
            
            # Get complete response text
            result_text = response.choices[0].message.content
            
            logger.info(f"✅ OpenAI response completed! Length: {len(result_text)} chars")
            logger.info(f"📄 COMPLETE OPENAI RESPONSE: {result_text[:2000]}..." if len(result_text) > 2000 else f"📄 COMPLETE OPENAI RESPONSE: {result_text}")
            
            # Clean the response - remove code blocks and extra formatting
            cleaned_response = self._clean_openai_response(result_text)
            logger.info(f"🧹 CLEANED RESPONSE: {cleaned_response[:1000]}..." if len(cleaned_response) > 1000 else f"🧹 CLEANED RESPONSE: {cleaned_response}")
            
            # Save response to file for debugging
            await self._save_response_to_file(result_text, cleaned_response, source_type, source_title)
            
            # Try to parse as JSON (expecting the new unified format)
            try:
                parsed_result = json.loads(cleaned_response)
                logger.info(f"✅ JSON parsing successful!")
                # The result should be in format: {"Source 1": {"link_and_source_name": "...", "information": {...}}}
            except json.JSONDecodeError as e:
                logger.warning(f"❌ OpenAI response is not valid JSON: {str(e)}")
                logger.warning(f"🔍 Cleaned response was: {cleaned_response[:500]}...")
                # If not JSON, create structured response in the expected format
                parsed_result = {
                    "Source 1": {
                        "link_and_source_name": f"{source_url} - {source_title}" if source_type == "url" else f"Text Source - {source_title}",
                        "information": {
                            "information_1": cleaned_response[:500] + "..." if len(cleaned_response) > 500 else cleaned_response
                        }
                    }
                }
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "success": True,
                "sources": parsed_result,
                "model_used": "gpt-4.1-2025-04-14",
                "processing_time": processing_time,
                "raw_response": result_text,
                "debug_info": {
                    "system_prompt_length": len(prompt['system']),
                    "user_prompt_length": len(prompt['user']),
                    "raw_response_length": len(result_text),
                    "cleaned_response_length": len(cleaned_response),
                    "json_parsing_successful": True,
                    "temperature": 1.0,
                    "max_tokens": 16384
                }
            }
            
        except Exception as e:
            logger.error(f"OpenAI processing failed: {str(e)}")
            return {
                "success": False,
                "error": f"AI processing failed: {str(e)}",
                "sources": {},
                "model_used": "",
                "processing_time": 0,
                "raw_response": "",
                "debug_info": {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "json_parsing_successful": False
                }
            }