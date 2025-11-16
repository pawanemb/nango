"""
🚀 Streaming Sources Service - CLEANED VERSION
Real-time sources collection with OpenRouter streaming support
"""

from typing import List, Dict, Any, Optional
import asyncio
from sqlalchemy.orm import Session
# Using simple dictionaries instead of complex schemas for better performance
from app.core.logging_config import logger
from app.services.fast_async_scraper import create_fast_scraper

from app.services.query_generation_prompts import QueryGenerationPrompts
from app.services.Sources_information_prompt import SourcesCollectionPrompts as InfoPrompts
from app.core.config import settings
from datetime import datetime, timezone
import uuid
import json
import re
from openai import AsyncOpenAI


class StreamingSourcesService:
    """Streaming service for real-time sources collection with OpenRouter AI processing"""

    def __init__(self, db: Session, user_id: str, project_id: Optional[str] = None, blog_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.blog_id = blog_id
        
        
        # Initialize fast async scraper for high-performance scraping
        self.fast_scraper = create_fast_scraper()
        
        # Initialize AsyncOpenAI client for query generation (same as streaming outline service)
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        logger.info(f"🚀 StreamingSourcesService initialized for user {user_id}")


    async def collect_sources_openrouter_focused_streaming(
        self,
        outline: List[Dict[str, Any]],
        primary_keyword: str = "",
        country: str = "us",
        blog_title: Optional[str] = None
    ):
        """🎯 FOCUSED STREAMING: Only OpenRouter processing updates"""
        
        try:
            # Convert outline to customizable format (SIMPLIFIED)
            customizable_outline = self._convert_outline_to_customizable_format(outline)
            
            logger.info(f"📋 Processing {len(customizable_outline['headings'])} headings with streaming")
            
            # Collect all subsections for parallel processing
            all_subsection_tasks = []
            
            # Create tasks for ALL processing units (headings and subsections)
            for heading_idx, heading in enumerate(customizable_outline['headings']):
                for subsection_idx, subsection in enumerate(heading['subsections']):
                    # Determine if this is a direct heading or actual subsection
                    is_direct_heading = (
                        len(heading['subsections']) == 1 and 
                        subsection['title'] == heading['title']
                    )
                    
                    task = self._stream_single_processing_unit_focused(
                        heading, subsection, primary_keyword, country, blog_title, outline, is_direct_heading
                    )
                    all_subsection_tasks.append((task, heading_idx, subsection_idx, heading, subsection, is_direct_heading))
            
            # 🚀 PARALLEL PROCESSING - Process ALL subsections concurrently!
            total_subsections = len(all_subsection_tasks)
            logger.info(f"🚀 Starting PARALLEL processing of {total_subsections} subsections")
            
            # Create queue for streaming updates from all parallel tasks
            update_queue = asyncio.Queue()
            completed_subsections = set()
            
            # Task to collect updates from all processing units
            async def collect_processing_unit_updates(task_gen, heading_idx, subsection_idx, heading, subsection, is_direct_heading):
                """Collect updates from a single processing unit and add to queue"""
                try:
                    async for update in task_gen:
                        # Add context to updates
                        update["heading_index"] = heading_idx
                        update["subsection_index"] = subsection_idx
                        update["heading_title"] = heading['title']
                        update["is_direct_heading"] = is_direct_heading
                        await update_queue.put(update)
                        
                    # Mark as completed
                    completed_subsections.add((heading_idx, subsection_idx))
                    
                except Exception as e:
                    unit_type = "heading" if is_direct_heading else "subsection"
                    logger.error(f"{unit_type.capitalize()} error for {subsection['title']}: {e}")
                    await update_queue.put({
                        "status": f"{unit_type}_error",
                        f"{unit_type}_title": subsection['title'],
                        "heading_index": heading_idx,
                        "subsection_index": subsection_idx,
                        "message": f"❌ Error processing {subsection['title']}: {str(e)}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "is_direct_heading": is_direct_heading
                    })
            
            # Start all tasks in parallel
            tasks = []
            for task_gen, heading_idx, subsection_idx, heading, subsection, is_direct_heading in all_subsection_tasks:
                task = asyncio.create_task(
                    collect_processing_unit_updates(task_gen, heading_idx, subsection_idx, heading, subsection, is_direct_heading)
                )
                tasks.append(task)
            
            # Stream updates as they arrive
            updates_received = 0
            while updates_received < total_subsections:
                try:
                    # Wait for update with timeout
                    update = await asyncio.wait_for(update_queue.get(), timeout=5.0)
                    yield update
                    
                    # Check if this is a completion or error update
                    if update.get("status") in ["subsection_completed", "subsection_error", "heading_completed", "heading_error"]:
                        updates_received += 1
                        unit_type = "heading" if update.get("is_direct_heading") else "subsection"
                        logger.info(f"📊 Progress: {updates_received}/{total_subsections} {unit_type}s completed")
                        
                except asyncio.TimeoutError:
                    # Check if all tasks completed
                    if len(completed_subsections) >= total_subsections:
                        break
                    continue
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Final completion event
            yield {
                "status": "processing_complete",
                "message": f"✅ All processing complete! {len(completed_subsections)} subsections processed.",
                "total_processed": total_subsections,
                "timestamp": datetime.now(timezone.utc).isoformat()
                # 📌 NOTE: Individual subsection data already sent in subsection_completed events
            }
            
        except Exception as e:
            logger.error(f"Streaming collection error: {str(e)}")
            yield {
                "status": "error",
                "message": f"Processing error: {str(e)}",
                "error_details": str(e)
            }


    async def _stream_single_processing_unit_focused(
        self,
        heading: Dict[str, Any],
        subsection: Dict[str, Any], 
        primary_keyword: str,
        country: str,
        blog_title: Optional[str],
        outline_json: List[Dict[str, Any]],
        is_direct_heading: bool = False
    ):
        """🎯 Process single processing unit (heading or subsection) - search + scrape + AI analysis"""
        try:
            # STEP 1: 🧠 Generate search queries using OpenAI (ASYNC)
            search_queries = await self._generate_five_search_queries_async(
                blog_title=blog_title or "",
                heading_title=heading['title'],
                subsection_title=subsection['title'],
                primary_keyword=primary_keyword,
                country=country,
                outline_json=outline_json
            )
            
            logger.info(f"🔍 Generated {len(search_queries)} queries for '{subsection['title']}'")
            
            if not search_queries:
                unit_type = "heading" if is_direct_heading else "subsection"
                yield {
                    "status": f"{unit_type}_error",
                    f"{unit_type}_title": subsection['title'],
                    "message": f"❌ No search queries generated for {subsection['title']}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                return
            
            # STEP 2: 🔍 Execute search queries in parallel (2 results per query)
            logger.info(f"🔍 Starting parallel search for {len(search_queries)} queries (expecting {len(search_queries) * 2} total results)")
            
            all_results = []
            all_query_tasks = []
            
            for query_idx, query in enumerate(search_queries):
                task = asyncio.create_task(
                    self.fast_scraper.scrape_and_search_pipeline(
                        query, 
                        max_results=2,  # Get 1st and 2nd results instead of just 1st
                        country=country
                    )
                )
                all_query_tasks.append((task, query, query_idx))
            
            # Wait for all search tasks to complete and stream successful websites
            for task, query, query_idx in all_query_tasks:
                try:
                    multiple_results = await task  # This returns a list of results (1st and 2nd)
                    
                    # Process each result (1st and 2nd) from this query
                    for result_idx, single_result in enumerate(multiple_results):
                        # Add query info to each result
                        single_result["source_query"] = query
                        single_result["query_index"] = query_idx
                        single_result["result_position"] = result_idx + 1  # 1 for 1st result, 2 for 2nd result
                        all_results.append(single_result)  # Add each result to list
                        
                        # 🌐 STREAM WEBSITE FOUND - Only for successful scrapes
                        if single_result.get("success", False):
                            unit_type = "heading" if is_direct_heading else "subsection"
                            yield {
                                "status": f"{unit_type}_website_found",
                                f"{unit_type}_title": subsection['title'],
                                "message": f"✅ Website found for {subsection['title']} (#{result_idx + 1})",
                                "website_data": {
                                    "url": single_result["url"],
                                    "title": single_result.get("title", "Unknown Source"),
                                    "position": result_idx + 1  # Show if it's 1st or 2nd result
                                },
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                except Exception as e:
                    logger.error(f"Query {query_idx} failed for '{query}': {e}")
            
            # STEP 3: 📊 Enhanced selection - we have max 10 results (5 queries × 2 results per query)
            successful_results = [r for r in all_results if r.get("success", False)]
            
            if not successful_results:
                unit_type = "heading" if is_direct_heading else "subsection"
                yield {
                    "status": f"{unit_type}_error",
                    f"{unit_type}_title": subsection['title'],
                    "message": f"❌ No successful results for {subsection['title']}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                return
            
            # STEP 4: 🤖 Process with OpenAI using proper prompts
            combined_sources = []
            for result in successful_results:
                combined_sources.append({
                    "url": result["url"],
                    "title": result.get("title", "Unknown Source"),
                    "content": result.get("content", ""),
                    "source_query": result.get("source_query", ""),
                    "query_index": result.get("query_index", 0)
                })
            
            # Get combined prompt using Sources_information_prompt.py
            combined_prompt = InfoPrompts.get_information_user_prompt(
                blog_title=blog_title,
                heading_title=heading['title'],
                subsection_title=subsection['title'],
                combined_sources=combined_sources,
                outline_json=json.dumps(outline_json, indent=2) if outline_json else None
            )
            
            # Process AI silently - no streaming updates
            final_content = {}
            async for openai_update in self._stream_openai_processing(
                combined_prompt, 
                subsection['title']
            ):
                if openai_update.get("status") == "openai_completed":
                    final_content = openai_update.get("final_content", {})
            
            # Process final result and update subsection (silent)
            if final_content:
                # Update subsection data with simple dictionary
                subsection["search_results"] = []  # Sources already sent in completion event
                subsection["is_processed"] = True
                
                # Create minimal response for streaming (no large payloads)
                source_details = [
                    {
                        "url": result["url"],
                        "title": result.get("title", "Unknown"),
                        "success": result.get("success", False)
                    } for result in successful_results
                ]
                
                unit_type = "heading" if is_direct_heading else "subsection"
                yield {
                    "status": f"{unit_type}_completed",
                    f"{unit_type}_title": subsection['title'],
                    "message": f"✅ Completed {subsection['title']} ({len(successful_results)} sources)",
                    "sources": source_details,  # Source details for immediate use
                    "informations": final_content,  # OpenAI analyzed content for mapping to outline
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
        except Exception as e:
            unit_type = "heading" if is_direct_heading else "subsection"
            logger.error(f"{unit_type.capitalize()} processing error for '{subsection['title']}': {str(e)}")
            yield {
                "status": f"{unit_type}_error",
                f"{unit_type}_title": subsection['title'],
                "message": f"❌ Error processing {subsection['title']}: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def _stream_openai_processing(
        self, 
        combined_prompt: str, 
        subsection_title: str
    ):
        """🎯 ASYNC OpenAI content analysis - using AsyncOpenAI like streaming outline service"""
        
        try:
            # Use AsyncOpenAI with responses.create (same as streaming outline service)
            response = await self.openai_client.responses.create(
                model="gpt-4o-mini-2024-07-18",  # Using same model as query generation for consistency
                input=[
                    {
                        "role": "system", 
                        "content": InfoPrompts.get_information_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": combined_prompt
                    }
                ],
                temperature=1.0,
                max_output_tokens=16384
            )
            
            # Extract content and clean markdown code blocks
            full_response = response.output_text
            # Clean markdown code blocks (```json and ```) and normalize newlines
            cleaned_response = re.sub(r'```json\s*|```\s*', '', full_response).strip()
            
            # Parse JSON to return as proper object instead of string
            try:
                parsed_ai_response = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI response as JSON: {e}")
                logger.info(f"🔧 Attempting to auto-fix JSON formatting...")
                
                # Try to auto-fix common JSON issues
                try:
                    fixed_response = self._fix_json_formatting(cleaned_response)
                    parsed_ai_response = json.loads(fixed_response)
                    logger.info(f"✅ Successfully auto-fixed JSON formatting")
                except Exception as fix_error:
                    logger.warning(f"❌ Auto-fix failed: {fix_error}")
                    parsed_ai_response = {"raw_response": cleaned_response, "parse_error": str(e)}
            logger.info(f"🤖 ASYNC OpenAI content analysis response length: {len(full_response)} chars")
            
            
            # Final OpenAI completion (single event instead of streaming)
            yield {
                "status": "openai_completed",
                "subsection_title": subsection_title,
                "message": f"✅ ASYNC AI processing complete ({len(cleaned_response)} chars)",
                "final_content": parsed_ai_response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"ASYNC OpenAI content analysis error for '{subsection_title}': {str(e)}")
            yield {
                "status": "openai_error",
                "subsection_title": subsection_title,
                "message": f"❌ ASYNC OpenAI error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def _generate_five_search_queries_async(
        self,
        blog_title: str,
        heading_title: str,
        subsection_title: str,
        primary_keyword: str,
        country: str,
        outline_json: List[Dict[str, Any]],
        current_datetime: str = None
    ) -> List[str]:
        """🔍 Generate 5 optimized search queries using OpenAI SDK - NO FALLBACKS"""
        
        try:
            # Convert outline to context string
            outline_context = json.dumps(outline_json, indent=2)
            
            # Get current datetime if not provided
            if current_datetime is None:
                current_datetime = datetime.now().strftime("%B %d, %Y at %I:%M %p")
            
            openai_start = datetime.now()
            logger.info(f"🧠 {openai_start.strftime('%H:%M:%S.%f')[:-3]} - Starting ASYNC OpenAI call for '{subsection_title}'")
            
            # Get query generation prompt using the same approach as title generation
            query_prompt = QueryGenerationPrompts.get_five_queries_generation_prompt(
                blog_title=blog_title or "",
                heading_title=heading_title,
                subsection_title=subsection_title,
                primary_keyword=primary_keyword,
                country=country,
                outline_context=outline_context,
                current_datetime=current_datetime
            )
            
            # 🚀 TRULY ASYNC: Use AsyncOpenAI for concurrent processing (same as streaming outline service)
            response = await self.openai_client.responses.create(
                model="gpt-4o-mini-2024-07-18",  # Fast and cost-effective for query generation
                input=[
                    {
                        "role": "system",
                        "content": QueryGenerationPrompts.get_system_message()
                    },
                    {
                        "role": "user",
                        "content": query_prompt
                    }
                ],
                temperature=0.3,
                max_output_tokens=300
            )
            
            openai_response_time = datetime.now()
            openai_duration = (openai_response_time - openai_start).total_seconds()
            logger.info(f"✅ {openai_response_time.strftime('%H:%M:%S.%f')[:-3]} - ASYNC OpenAI responded for '{subsection_title}' in {openai_duration:.3f}s")
            
            ai_response = response.output_text.strip()
            
            
            # Parse JSON response - NO FALLBACKS
            try:
                # Clean up markdown code blocks if present
                cleaned_response = re.sub(r'```json\s*|\s*```', '', ai_response).strip()
                queries_data = json.loads(cleaned_response)
                
                # Extract the 5 queries
                queries = [
                    queries_data.get("query_1", ""),
                    queries_data.get("query_2", ""),
                    queries_data.get("query_3", ""),
                    queries_data.get("query_4", ""),
                    queries_data.get("query_5", "")
                ]
                
                # Filter out empty queries and return valid ones
                valid_queries = [q.strip() for q in queries if q and q.strip()]
                
                logger.info(f"✅ Generated {len(valid_queries)} queries for '{subsection_title}': {valid_queries}")
                return valid_queries
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse query generation response: {e}")
                logger.error(f"Raw response: {ai_response}")
                return []
                
        except Exception as e:
            logger.error(f"ASYNC Query generation error for '{subsection_title}': {str(e)}")
            return []

    def _fix_json_formatting(self, json_string: str) -> str:
        """Fix common JSON formatting issues in AI responses"""
        
        # Fix missing commas before closing quotes
        # Pattern: "text" \n "text" -> "text", \n "text"
        fixed = re.sub(r'"\s*\n\s*"', '",\n      "', json_string)
        
        # Fix missing commas before closing braces
        # Pattern: "text" \n } -> "text" \n }
        fixed = re.sub(r'"\s*\n\s*}', '"\n    }', fixed)
        
        # Fix missing commas between information entries
        # Pattern: } \n "information_X" -> }, \n "information_X"
        fixed = re.sub(r'}\s*\n\s*"information_', '},\n      "information_', fixed)
        
        # Fix missing commas between Source entries
        # Pattern: } \n "Source_X" -> }, \n "Source_X" 
        fixed = re.sub(r'}\s*\n\s*"Source_', '},\n  "Source_', fixed)
        
        # Fix trailing comma issues before closing braces
        fixed = re.sub(r',\s*}', '\n    }', fixed)
        fixed = re.sub(r',\s*]', '\n  ]', fixed)
        
        return fixed



    def _convert_outline_to_customizable_format(self, outline) -> Dict[str, Any]:
        """Convert outline to customizable format - SIMPLIFIED for actual payload format"""
        
        customizable_headings = []
        
        # Handle outline array format: [{"heading": "...", "subsections": [...]}]
        if isinstance(outline, list):
            logger.info(f"Processing {len(outline)} outline sections")
            
            for order, section in enumerate(outline, 1):
                if not isinstance(section, dict):
                    continue
                
                # Extract heading and subsections from actual payload format
                heading_title = section.get("heading", f"Heading {order}")
                subsections = section.get("subsections", [])
                
                # Create subsections
                custom_subsections = []
                
                if subsections:
                    # Normal case: heading has subsections
                    for sub_order, subsection in enumerate(subsections, 1):
                        if isinstance(subsection, str):
                            subsection_title = subsection
                        elif isinstance(subsection, dict):
                            subsection_title = subsection.get("title", f"Subsection {sub_order}")
                        else:
                            continue
                            
                        data_point = {
                            "id": str(uuid.uuid4()),
                            "title": subsection_title,
                            "search_results": [],
                            "data_type": "generated",
                            "order": sub_order
                        }
                        custom_subsections.append(data_point)
                else:
                    # Special case: heading has no subsections - treat heading itself as subsection
                    logger.info(f"Processing '{heading_title}' as direct subsection (no subsections array)")
                    data_point = {
                        "id": str(uuid.uuid4()),
                        "title": heading_title,  # Use heading title as subsection title
                        "search_results": [],
                        "data_type": "generated",
                        "order": 1
                    }
                    custom_subsections.append(data_point)
                
                # Add heading if it has valid subsections
                if custom_subsections:
                    custom_heading = {
                        "id": str(uuid.uuid4()),
                        "title": heading_title,
                        "subsections": custom_subsections,
                        "order": order
                    }
                    customizable_headings.append(custom_heading)
                    logger.info(f"Added '{heading_title}' with {len(custom_subsections)} subsections")
        
        else:
            logger.error(f"Invalid outline format: {type(outline)}")
            raise ValueError(f"Invalid outline format. Expected list, got {type(outline)}")
        
        logger.info(f"✅ Converted outline: {len(customizable_headings)} headings")
        
        return {
            "blog_id": "",
            "headings": customizable_headings,
            "conclusion": "Conclusion",
            "faqs": [],
            "status": "draft"
        }