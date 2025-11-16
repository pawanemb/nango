"""
🔗 Simple Custom Source Service - URL Processing Only
Clean implementation: Scrape URL → OpenAI Analysis → Return Information List
"""

from typing import Dict, Any, List
import asyncio
import time
from sqlalchemy.orm import Session
from app.core.logging_config import logger
from app.services.rayo_scraper import create_rayo_scraper_compat
from app.services.add_custom_source_pdf_prompt import AddCustomSourcePrompt
from app.core.config import settings
from openai import AsyncOpenAI
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
from app.services.digitalocean_spaces_service import DigitalOceanSpacesService
import json
import re
import uuid
from datetime import datetime

class AddCustomSourceService:
    """Simple service for URL scraping and OpenAI processing"""
    
    def __init__(self, db: Session, user_id: str, project_id: str):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        
        # Initialize Rayo scraper
        self.rayo_scraper = create_rayo_scraper_compat(user_id)
        
        # Initialize OpenAI client
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)
        
        # Initialize DigitalOcean Spaces service for PDF uploads
        self.storage_service = DigitalOceanSpacesService()
        
        logger.info(f"🔗 AddCustomSourceService initialized for user {user_id}")
    
    async def process_url_source(self, url: str, blog_id: str, heading: str = None, subsection: str = None) -> Dict[str, Any]:
        """Process URL: Scrape → OpenAI → Return information list"""
        
        start_time = time.time()
        
        try:
            # 🚀 STEP 1: Scrape URL using RayoScrapingService
            logger.info(f"🔍 Starting URL scraping with RayoScraper: {url}")
            
            scrape_result = await self.rayo_scraper.scrape_website(
                url=url,
                project_id=self.project_id,
                blog_id=blog_id,
                additional_metadata={
                    "comments": "Add custom_source"
                }
            )
            
            if scrape_result.get("status") != "completed":
                return {
                    "success": False,
                    "error": f"Failed to scrape URL: {scrape_result.get('error', 'Unknown scraping error')}"
                }
            
            scraped_content = scrape_result.get("content", "")
            scraped_length = len(scraped_content)
            
            if scraped_length < 50:
                return {
                    "success": False,
                    "error": "Scraped content too short. Website may be blocking access or has no text content."
                }
            
            logger.info(f"✅ URL scraped successfully with RayoScraper: {scraped_length} characters, method: {scrape_result.get('strategy_used', 'unknown')}")
            
            # 🚀 STEP 2: Process with OpenAI
            logger.info("🤖 Processing content with OpenAI")
            
            openai_result = await self._process_content_with_openai(
                content=scraped_content,
                url=url,
                heading=heading,
                subsection=subsection
            )
            
            if not openai_result["success"]:
                # Pass through the original error details for "No information found"
                if openai_result.get('error') == 'No information found':
                    return {
                        "success": False,
                        "error": openai_result.get('error'),
                        "raw_response": openai_result.get('raw_response', '')
                    }
                else:
                    return {
                        "success": False,
                        "error": f"OpenAI processing failed: {openai_result.get('error', 'Unknown AI error')}"
                    }
            
            processing_time = time.time() - start_time
            
            # 🚀 STEP 3: Format Final Result
            return {
                "success": True,
                "scraped_length": scraped_length,
                "parsed_response": openai_result.get("parsed_response", {}),
                "citation": openai_result.get("citation", f"Source: {url}"),
                "processing_time": round(processing_time, 2),
                "ai_model": "gpt-4.1-2025-04-14",
                "input_tokens": openai_result.get("input_tokens", 0),
                "output_tokens": openai_result.get("output_tokens", 0),
                "total_tokens": openai_result.get("total_tokens", 0)
            }
            
        except Exception as e:
            logger.error(f"Error processing URL source: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_pdf_file(self, pdf_content: bytes, original_filename: str, blog_id: str, heading: str = None, subsection: str = None, source_name: str = None) -> Dict[str, Any]:
        """Process PDF file: Upload to Storage → Generate CDN URL → Process with RayoScraper → OpenAI Analysis"""
        
        start_time = time.time()
        
        try:
            # 🚀 STEP 1: Upload PDF to DigitalOcean Spaces in 'dump' folder
            logger.info(f"📤 Uploading PDF file to DigitalOcean Spaces: {original_filename}")
            
            # Generate unique filename for dump folder
            timestamp = int(time.time())
            random_hash = uuid.uuid4().hex[:8]
            file_ext = '.pdf'
            unique_filename = f"dump_{timestamp}_{random_hash}{file_ext}"
            
            # Upload to dump folder in spaces
            upload_result = await self._upload_pdf_to_dump_folder(
                pdf_content=pdf_content,
                filename=unique_filename,
                original_filename=original_filename
            )
            
            if not upload_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to upload PDF: {upload_result.get('error', 'Unknown upload error')}"
                }
            
            # Get the CDN URL
            pdf_url = upload_result["public_url"]
            logger.info(f"✅ PDF uploaded successfully: {pdf_url}")
            
            # 🚀 STEP 2: Process the PDF URL using modified processing logic with custom source name
            logger.info(f"🔍 Processing uploaded PDF via RayoScraper: {pdf_url}")
            
            # Use custom PDF processing instead of generic URL processing
            url_processing_result = await self._process_pdf_with_custom_source_name(
                pdf_url=pdf_url,
                blog_id=blog_id,
                heading=heading,
                subsection=subsection,
                source_name=source_name or original_filename,
                original_filename=original_filename
            )
            
            # Add upload metadata to the result
            if url_processing_result["success"]:
                url_processing_result["pdf_upload_info"] = {
                    "original_filename": original_filename,
                    "storage_path": upload_result["storage_path"],
                    "pdf_url": pdf_url,
                    "file_size": len(pdf_content)
                }
            
            processing_time = time.time() - start_time
            url_processing_result["total_processing_time"] = round(processing_time, 2)
            
            return url_processing_result
            
        except Exception as e:
            logger.error(f"Error processing PDF file: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _upload_pdf_to_dump_folder(self, pdf_content: bytes, filename: str, original_filename: str) -> Dict[str, Any]:
        """Upload PDF to dump folder in DigitalOcean Spaces"""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Create storage path in dump folder
            storage_path = f"dump/{filename}"
            
            # Sanitize metadata values to ASCII only for S3 compatibility
            def sanitize_metadata_value(value: str) -> str:
                """Convert non-ASCII characters to ASCII equivalents"""
                # Replace common non-ASCII characters
                replacements = {
                    '—': '-',  # em dash
                    '–': '-',  # en dash
                    ''': "'",  # left single quotation mark
                    ''': "'",  # right single quotation mark
                    '"': '"',  # left double quotation mark
                    '"': '"',  # right double quotation mark
                    '…': '...',  # ellipsis
                }
                
                sanitized = value
                for old, new in replacements.items():
                    sanitized = sanitized.replace(old, new)
                
                # Encode to ASCII, replacing any remaining non-ASCII chars
                try:
                    return sanitized.encode('ascii', 'replace').decode('ascii')
                except Exception:
                    # Fallback: remove all non-ASCII characters
                    return ''.join(char if ord(char) < 128 else '_' for char in sanitized)
            
            # Upload to DigitalOcean Spaces
            self.storage_service.s3_client.put_object(
                Bucket=self.storage_service.bucket_name,
                Key=storage_path,
                Body=pdf_content,
                ContentType='application/pdf',
                CacheControl='public, max-age=31536000',  # 1 year cache
                ACL='public-read',  # Make file publicly accessible
                Metadata={
                    'original_filename': sanitize_metadata_value(original_filename),
                    'uploaded_by': sanitize_metadata_value(self.user_id),
                    'project_id': sanitize_metadata_value(self.project_id)
                }
            )
            
            logger.info(f"Successfully uploaded PDF to DigitalOcean Spaces: {storage_path}")
            
            # Generate CDN URL
            from app.core.config import settings
            import os
            cdn_base_url = getattr(settings, 'CDN_BASE_URL', os.getenv('CDN_BASE_URL', 'https://cdn.rayo.work'))
            public_url = f"{cdn_base_url}/{storage_path}"
            
            return {
                "success": True,
                "storage_path": storage_path,
                "public_url": public_url,
                "filename": filename,
                "original_filename": original_filename,
                "file_size": len(pdf_content)
            }
            
        except ClientError as e:
            error_msg = f"DigitalOcean Spaces PDF upload failed: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            logger.error(f"Error uploading PDF to dump folder: {str(e)}")
            return {
                "success": False,
                "error": f"PDF upload error: {str(e)}"
            }
    
    async def _process_pdf_with_custom_source_name(self, pdf_url: str, blog_id: str, heading: str = None, subsection: str = None, source_name: str = None, original_filename: str = None) -> Dict[str, Any]:
        """Process PDF URL with custom source name support"""
        
        try:
            # 🚀 STEP 1: Scrape PDF URL using RayoScrapingService
            logger.info(f"🔍 Starting PDF scraping with RayoScraper: {pdf_url}")
            
            scrape_result = await self.rayo_scraper.scrape_website(
                url=pdf_url,
                project_id=self.project_id,
                blog_id=blog_id,
                additional_metadata={
                    "comments": "Add custom_source PDF",
                    "original_filename": original_filename,
                    "source_name": source_name
                }
            )
            
            if scrape_result.get("status") != "completed":
                return {
                    "success": False,
                    "error": f"Failed to scrape PDF: {scrape_result.get('error', 'Unknown scraping error')}"
                }
            
            scraped_content = scrape_result.get("content", "")
            scraped_length = len(scraped_content)
            
            if scraped_length < 50:
                return {
                    "success": False,
                    "error": "Scraped PDF content too short. PDF may be protected or has no extractable text content."
                }
            
            logger.info(f"✅ PDF scraped successfully with RayoScraper: {scraped_length} characters, method: {scrape_result.get('strategy_used', 'unknown')}")
            
            # 🚀 STEP 2: Process with OpenAI using custom source name
            logger.info(f"🤖 Processing PDF content with OpenAI, source: {source_name}")
            
            openai_result = await self._process_content_with_openai_custom_source(
                content=scraped_content,
                source_name=source_name,
                heading=heading,
                subsection=subsection
            )
            
            if not openai_result["success"]:
                # Pass through the original error details for "No information found"
                if openai_result.get('error') == 'No information found':
                    return {
                        "success": False,
                        "error": openai_result.get('error'),
                        "raw_response": openai_result.get('raw_response', '')
                    }
                else:
                    return {
                        "success": False,
                        "error": f"OpenAI processing failed: {openai_result.get('error', 'Unknown AI error')}"
                    }
            
            # 🚀 STEP 3: Format Final Result
            return {
                "success": True,
                "scraped_length": scraped_length,
                "parsed_response": openai_result.get("parsed_response", {}),
                "citation": openai_result.get("citation", f"Source: {source_name}"),
                "ai_model": "gpt-4.1-2025-04-14",
                "input_tokens": openai_result.get("input_tokens", 0),
                "output_tokens": openai_result.get("output_tokens", 0),
                "total_tokens": openai_result.get("total_tokens", 0)
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF with custom source name: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _process_content_with_openai_custom_source(self, content: str, source_name: str, heading: str = None, subsection: str = None) -> Dict[str, Any]:
        """Process scraped content with OpenAI using custom source name (like text service)"""
        
        try:
            # Use AddCustomSourceTextPrompt for custom source name support
            from app.services.add_custom_source_text_prompt import AddCustomSourceTextPrompt
            
            # Get system and user prompts from text prompt file (supports source_name)
            system_prompt = AddCustomSourceTextPrompt.get_system_prompt()
            user_prompt = AddCustomSourceTextPrompt.get_user_prompt(source_name, content, heading, subsection)

            # Make OpenAI API call
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=16384
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # 🚀 RECORD USAGE IMMEDIATELY AFTER API CALL - BEFORE PARSING
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            
            logger.info("💰 BILLING: Recording usage for PDF processing with custom source name")
            self._record_usage_with_source_name(
                source_name=source_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_name="gpt-4.1-2025-04-14"
            )
            
            # Extract content and clean markdown code blocks
            full_response = ai_response
            # Clean markdown code blocks (```json and ```) and normalize newlines
            cleaned_response = re.sub(r'```json\s*|```\s*', '', full_response).strip()
            
            # Parse JSON to return as proper object instead of string
            try:
                parsed_ai_response = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI response as JSON: {e}")
                logger.warning(f"Raw OpenAI response: '{cleaned_response}'")
                # Check if empty or "No information found"
                if not cleaned_response.strip() or cleaned_response.strip() == "No information found":
                    logger.info("OpenAI returned empty or 'No information found' - treating as error BUT ALREADY BILLED")
                    return {
                        "success": False,
                        "error": "No information found",
                        "raw_response": cleaned_response,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": response.usage.total_tokens if response.usage else 0
                    }
                parsed_ai_response = {"raw_response": cleaned_response, "parse_error": str(e)}
            
            logger.info(f"✅ OpenAI processed PDF content: {len(full_response)} characters")
            
            return {
                "success": True,
                "parsed_response": parsed_ai_response,  # Parsed JSON response
                "citation": f"{source_name}",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as e:
            logger.error(f"OpenAI processing error with custom source: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _record_usage_with_source_name(self, source_name: str, input_tokens: int, output_tokens: int, model_name: str):
        """Record usage for custom PDF source processing with source name"""
        try:
            logger.info("🔔 USAGE TRACKING STARTED - Custom PDF Source Processing")
            logger.info(f"📊 RAW USAGE DATA:")
            logger.info(f"   📧 User ID: {self.user_id}")
            logger.info(f"   📄 Source: {source_name}")
            logger.info(f"   🤖 Model: {model_name}")
            logger.info(f"   📥 Input Tokens: {input_tokens}")
            logger.info(f"   📤 Output Tokens: {output_tokens}")
            logger.info(f"   📊 Total Tokens: {input_tokens + output_tokens}")
            logger.info(f"   🏢 Project ID: {self.project_id}")
            
            metadata = {
                "add_custom_source": {
                    "source_name": source_name,
                    "model": model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "service_type": "pdf_upload_processing_and_analysis"
                }
            }
            
            logger.info(f"📦 METADATA PREPARED: {metadata}")
            
            logger.info("🚀 CALLING EnhancedLLMUsageService.record_llm_usage()...")
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="add_custom_source",  # Matches service_multipliers.py
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                service_description="Custom PDF source upload and processing with AI analysis",
                project_id=self.project_id,
                additional_metadata=metadata
            )
            
            logger.info(f"✅ USAGE RECORDING SUCCESS!")
            logger.info(f"💰 BILLING RESULT: {result}")
            logger.info(f"🔔 USAGE TRACKING COMPLETED - Custom PDF Source Processing")
            
        except Exception as e:
            logger.error(f"❌ USAGE TRACKING FAILED - Custom PDF Source Processing")
            logger.error(f"🔥 ERROR DETAILS: {str(e)}")
            logger.error(f"📧 User ID: {self.user_id}")
            logger.error(f"📄 Source: {source_name}")
            logger.error(f"📊 Tokens: {input_tokens}/{output_tokens}")
            # Don't raise here to avoid breaking the main workflow
    
    async def _process_content_with_openai(self, content: str, url: str, heading: str = None, subsection: str = None) -> Dict[str, Any]:
        """Process scraped content with OpenAI using custom source prompt"""
        
        try:
            # Get system and user prompts from prompt file
            system_prompt = AddCustomSourcePrompt.get_system_prompt()
            user_prompt = AddCustomSourcePrompt.get_user_prompt(url, content, heading, subsection)

            # Make OpenAI API call
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=16384
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # 🚀 RECORD USAGE IMMEDIATELY AFTER API CALL - BEFORE PARSING
            # This ensures we bill even if OpenAI returns "No information found"
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            
            logger.info("💰 BILLING: Recording usage regardless of response content")
            self._record_usage(
                url=url,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_name="gpt-4.1-2025-04-14"
            )
            
            # Extract content and clean markdown code blocks (same as streaming_sources_service.py)
            full_response = ai_response
            # Clean markdown code blocks (```json and ```) and normalize newlines
            cleaned_response = re.sub(r'```json\s*|```\s*', '', full_response).strip()
            
            # Parse JSON to return as proper object instead of string
            try:
                parsed_ai_response = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI response as JSON: {e}")
                logger.warning(f"Raw OpenAI response: '{cleaned_response}'")
                # Check if empty or "No information found"
                if not cleaned_response.strip() or cleaned_response.strip() == "No information found":
                    logger.info("OpenAI returned empty or 'No information found' - treating as error BUT ALREADY BILLED")
                    return {
                        "success": False,
                        "error": "No information found",
                        "raw_response": cleaned_response,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": response.usage.total_tokens if response.usage else 0
                    }
                parsed_ai_response = {"raw_response": cleaned_response, "parse_error": str(e)}
            
            logger.info(f"✅ OpenAI processed content: {len(full_response)} characters")
            
            return {
                "success": True,
                "parsed_response": parsed_ai_response,  # Parsed JSON response
                "citation": f"{url}",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as e:
            logger.error(f"OpenAI processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _record_usage(self, url: str, input_tokens: int, output_tokens: int, model_name: str):
        """Record usage for custom source processing"""
        try:
            logger.info("🔔 USAGE TRACKING STARTED - Custom Source Processing")
            logger.info(f"📊 RAW USAGE DATA:")
            logger.info(f"   📧 User ID: {self.user_id}")
            logger.info(f"   🔗 URL: {url}")
            logger.info(f"   🤖 Model: {model_name}")
            logger.info(f"   📥 Input Tokens: {input_tokens}")
            logger.info(f"   📤 Output Tokens: {output_tokens}")
            logger.info(f"   📊 Total Tokens: {input_tokens + output_tokens}")
            logger.info(f"   🏢 Project ID: {self.project_id}")
            
            metadata = {
                "add_custom_source": {
                    "url": url,
                    "model": model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "service_type": "url_processing_and_analysis"
                }
            }
            
            logger.info(f"📦 METADATA PREPARED: {metadata}")
            
            logger.info("🚀 CALLING EnhancedLLMUsageService.record_llm_usage()...")
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="add_custom_source",  # Matches service_multipliers.py
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                service_description="Custom source URL processing with AI analysis",
                project_id=self.project_id,
                additional_metadata=metadata
            )
            
            logger.info(f"✅ USAGE RECORDING SUCCESS!")
            logger.info(f"💰 BILLING RESULT: {result}")
            logger.info(f"🔔 USAGE TRACKING COMPLETED - Custom Source Processing")
            
        except Exception as e:
            logger.error(f"❌ USAGE TRACKING FAILED - Custom Source Processing")
            logger.error(f"🔥 ERROR DETAILS: {str(e)}")
            logger.error(f"📧 User ID: {self.user_id}")
            logger.error(f"🔗 URL: {url}")
            logger.error(f"📊 Tokens: {input_tokens}/{output_tokens}")
            # Don't raise here to avoid breaking the main workflow
    
    def _create_simple_citation(self, url: str) -> str:
        """Create a simple citation for the URL source"""
        return f"Retrieved from {url} on {datetime.now().strftime('%Y-%m-%d')}"