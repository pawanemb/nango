from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import os
from openai import OpenAI
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging_config import logger
from app.models.project import Project
from app.tasks.keyword_suggestions import fetch_metrics  # Import the async function
from app.db.session import get_db_session
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
from app.services.country_service import CountryService

class SecondaryKeywordsService:
    def __init__(self, 
                 db: Session,
                 user_id: str,
                 project_id: Optional[str] = None,
                 openai_api_key: Optional[str] = None, 
                 database_uri: str = None):
        """
        Initialize SecondaryKeywordsService.
        
        :param db: Database session
        :param user_id: User ID for tracking
        :param project_id: Project ID for tracking
        :param openai_api_key: OpenAI API key. If not provided, uses settings.
        :param database_uri: Database URI for centralized PostgreSQL service
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.openai_client = OpenAI(
            api_key=openai_api_key or getattr(settings, 'OPENAI_API_KEY', 
                                              os.getenv('OPENAI_API_KEY'))
        )
        self.logger = logger
        self.database_uri = database_uri
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)
        
        # Initialize usage tracking variables
        self.keyword_generation_usage = None
        self.intent_analysis_usage = None




    def get_keyword_intent_with_tracking(self, keywords: List[str]) -> List[str]:
        """
        Get keyword intent with usage tracking for billing.
        
        :param keywords: List of keywords to analyze
        :return: List of intent classifications
        """
        try:
            from app.prompts.blogGenerator.keyword_intent_prompt import gpt_keyword_intent_prompt
            
            # Generate prompt
            prompt_data = gpt_keyword_intent_prompt(keywords)
            self.logger.info(f"OpenAI intent analysis REQUEST: {{\n  system: '{prompt_data['system']}',\n  user: '{prompt_data['user']}'\n}}")
            
            # Call OpenAI API and capture usage data
            response = self.openai_client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                    {"role": "system", "content": prompt_data["system"]},
                    {"role": "user", "content": prompt_data["user"]}
                ],
                temperature=1,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Store usage data for combined tracking
            self.intent_analysis_usage = {
                "model_name": response.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "metadata": {
                    "keywords_count": len(keywords),
                    "keywords": keywords,
                    "prompt_type": "intent_analysis"
                }
            }
            
            # Extract and process intents
            intents_text = response.output_text.strip()
            self.logger.info(f"OpenAI intent analysis RESPONSE: {intents_text}")
            
            intents_list = [intent.strip() for intent in intents_text.split(',')]
            
            # Log intent mappings
            for i, keyword in enumerate(keywords):
                if i < len(intents_list):
                    self.logger.info(f"Intent mapping: '{keyword}' -> '{intents_list[i]}'")
                else:
                    self.logger.warning(f"No intent found for keyword: '{keyword}'")
            
            return intents_list
            
        except Exception as e:
            self.logger.error(f"Error getting keyword intent with tracking: {str(e)}")
            raise

    def fetch_metrics(
        self, 
        keywords: List[str], 
        country: str = "in"
    ) -> List[Dict[str, Any]]:
        """
        Fetch metrics for keywords asynchronously.
        
        :param keywords: List of keywords
        :param country: Country for localization
        :return: List of keyword metrics
        """
        INTENT_MAPPING = {
            "0": "commercial",
            "1": "informational",
            "2": "navigational",
            "3": "transactional",
            "": "unknown"
        }
        try:
            # Log the metrics fetch request
            logger.info(f"Metrics fetch REQUEST: keywords={keywords}, country={country}")

            # Ensure all inputs are basic Python types
            clean_keywords = list(map(str, keywords))
            metrics = fetch_metrics(clean_keywords, str(country))
            
            # Log the raw metrics response
            logger.info(f"Metrics fetch RAW RESPONSE: {metrics}")
            
            # Convert all values to basic Python types
            serializable_metrics = []
            for metric in metrics:
                serializable_metrics.append({
                    "keyword": str(metric["keyword"]),
                    "search_volume": int(metric.get("search_volume", 0)),
                    "difficulty": int(metric.get("difficulty", 0)),
                    "intent": str(INTENT_MAPPING.get(metric.get("intent"),"unknown"))
                })
            
            # Log the processed metrics
            logger.info(f"Metrics fetch PROCESSED RESPONSE: {serializable_metrics}")
            
            return serializable_metrics
            
        except Exception as e:
            self.logger.error(f"Error fetching metrics: {e}")
            raise

    def process_results(
        self, 
        metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process and sort keyword metrics.
        
        :param metrics: List of keyword metrics
        :return: Processed and sorted keyword results
        """
        try:
            # Sort by search volume descending
            sorted_metrics = sorted(
                metrics,
                key=lambda x: x.get('search_volume', 0),
                reverse=True
            )
            
            return {
                "keywords": sorted_metrics,
                "generated_at": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error processing results: {e}")
            raise

    def _record_manual_analysis_usage(self, project_id: str, keywords: List[str], country: str):
        """
        Record usage for manual keyword analysis (intent analysis only)
        """
        try:
            if not self.intent_analysis_usage:
                self.logger.warning("Missing usage data for manual analysis tracking")
                return
            
            # Use the intent analysis usage data
            model_name = self.intent_analysis_usage["model_name"]
            input_tokens = self.intent_analysis_usage["input_tokens"]
            output_tokens = self.intent_analysis_usage["output_tokens"]
            
            # Structure metadata for manual analysis (simplified)
            manual_metadata = {
                "secondary_keywords_manual": {
                    "analysis_type": "manual_intent_analysis",
                    "keywords_count": len(keywords)
                }
            }
            
            # Record usage for manual analysis
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="secondary_keywords_manual",
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                service_description="Manual secondary keyword analysis with intent classification",
                project_id=project_id,
                additional_metadata=manual_metadata
            )
            
            self.logger.info(f"✅ Recorded manual analysis usage: {result}")
            
        except Exception as e:
            self.logger.error(f"Failed to record manual analysis usage: {e}")
            # Don't raise here to avoid breaking the main workflow

    def generate_secondary_keywords_with_intent(
        self,
        primary_keyword: str,
        project_id: str,
        country: str = "in",
        intent: str = ""
    ) -> List[Dict[str, str]]:
        """
        Generate secondary keywords WITH intent classification in single AI call.
        Returns list of {"keyword": "...", "intent": "..."} objects.
        """
        try:
            # Update project_id if provided
            if project_id:
                self.project_id = project_id
                
            # Get project details from database
            project = None
            with get_db_session() as db:
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project:
                    raise ValueError(f"Project not found with id: {project_id}")

            # Extract language preference from project
            language_preference = "en"  # Default fallback
            if project.languages and len(project.languages) > 0:
                language_preference = project.languages[0]
                logger.info(f"Extracted language preference: '{language_preference}'")
            else:
                logger.warning(f"No language preference found, using default: '{language_preference}'")

            # Convert country code to region name using existing service with fallback
            try:
                region_name = CountryService.get_country_name(country.upper())
                logger.info(f"🌍 Using region: {region_name} for web search (country code: {country})")
            except (ValueError, Exception) as e:
                logger.warning(f"Invalid country code '{country}': {e}. Using fallback region.")
                region_name = "India"  # Default fallback
                logger.info(f"🌍 Fallback to region: {region_name}")

            # Generate the optimized prompt with intent
            from app.prompts.blogGenerator.secondary_keywords_with_intent_prompt import secondary_keywords_with_intent_prompt
            prompt_data = secondary_keywords_with_intent_prompt(primary_keyword, project, country, intent, language_preference)
            logger.info(f"🚀 OPTIMIZED OpenAI REQUEST: Single call for keywords + intent")
            
            # Call OpenAI API with web search and capture usage data
            response = self.openai_client.responses.create(
                model=settings.OPENAI_MODEL_4_1,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt_data["system"]
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt_data["user"]
                            }
                        ]
                    }
                ],
                text={
                    "format": {
                        "type": "text"
                    }
                },
                reasoning={},
                tools=[
                    {
                        "type": "web_search_preview",
                        "user_location": {
                            "type": "approximate",
                            "region": region_name
                        },
                        "search_context_size": "medium"
                    }
                ],
                tool_choice={
                    "type": "web_search_preview"
                },
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS,
                top_p=1,
                store=True,
                include=["web_search_call.action.sources"]
            )
            
            # Store usage data for billing
            self.keyword_generation_usage = {
                "model_name": response.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "metadata": {
                    "primary_keyword": primary_keyword,
                    "country": country,
                    "intent": intent,
                    "language_preference": language_preference,
                    "prompt_type": "keywords_with_intent_generation",
                    "optimization": "single_ai_call"
                }
            }
            
            # Parse JSON response
            response_text = response.output_text.strip()
            logger.info(f"🎯 OPTIMIZED OpenAI RESPONSE with WEB SEARCH: {response_text}")
            
            # Log web search sources if available
            if hasattr(response, 'web_search_call') and response.web_search_call:
                logger.info(f"🔍 Web search sources used: {response.web_search_call.action.sources}")
            else:
                logger.info(f"🔍 Web search data included in response generation")
            
            try:
                import json
                # Clean JSON response
                json_text = response_text
                if json_text.startswith('```json'):
                    json_text = json_text[7:]
                if json_text.endswith('```'):
                    json_text = json_text[:-3]
                json_text = json_text.strip()
                
                # Parse JSON
                parsed_data = json.loads(json_text)
                keywords_with_intent = parsed_data.get("keywords", [])
                
                logger.info(f"✅ Parsed {len(keywords_with_intent)} keywords with intent in single call")
                
                return keywords_with_intent
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw response: {response_text}")
                
                # Fallback: Return empty list if JSON parsing fails
                logger.warning("JSON parsing failed, returning empty keywords list")
                return []
                
        except Exception as e:
            logger.error(f"Error generating keywords with intent: {str(e)}")
            raise

    def generate_secondary_keywords_workflow(
        self,
        primary_keyword: str,
        project_id: str,
        country: str = "in",
        intent: str = ""
    ) -> Dict[str, Any]:
        try:
            logger.info(f"🚀 Starting OPTIMIZED secondary keywords workflow for: {primary_keyword}")
            
            # Initialize usage tracking variables
            self.keyword_generation_usage = None
            # No longer need intent_analysis_usage - single AI call handles both!
            
            # STEP 1: Generate keywords WITH intent in single AI call
            logger.info(f"🎯 Generating keywords + intent in single optimized AI call")
            keywords_with_intent = self.generate_secondary_keywords_with_intent(
                primary_keyword, project_id, country, intent
            )
            logger.info(f"✅ Generated {len(keywords_with_intent)} keywords with intent")
            
            # Extract just keywords for metrics fetching
            keywords = [item["keyword"] for item in keywords_with_intent]
            
            # STEP 2: Fetch metrics from SEMrush
            logger.info(f"📊 Fetching SEMrush metrics for {len(keywords)} keywords")
            metrics = self.fetch_metrics(keywords, country)
            logger.info(f"✅ Fetched metrics data")

            # STEP 3: Record single AI call usage for billing (much cheaper!)
            self._record_optimized_generation_usage(project_id, primary_keyword, country)
            
            # STEP 4: Merge AI intent data with SEMrush metrics
            logger.info(f"🔗 Merging AI intent data with SEMrush metrics")
            processed_results = self._merge_intent_with_metrics(keywords_with_intent, metrics)
            
            logger.info(f"🎉 OPTIMIZED workflow completed successfully!")
            return processed_results
            
        except Exception as e:
            logger.error(f"Optimized secondary keyword workflow failed: {e}")
            raise

    def _record_optimized_generation_usage(self, project_id: str, primary_keyword: str, country: str):
        """Record usage for single optimized AI call (much cheaper than dual calls)"""
        try:
            if not self.keyword_generation_usage:
                logger.warning("Missing usage data for optimized generation tracking")
                return
            
            # Single call metadata
            optimized_metadata = {
                "secondary_keywords_generation_optimized": {
                    "optimization_type": "single_ai_call",
                    "calls_made": 1,  # Instead of 2!
                    "model": self.keyword_generation_usage["model_name"],
                    "input_tokens": self.keyword_generation_usage["input_tokens"],
                    "output_tokens": self.keyword_generation_usage["output_tokens"],
                    "features": ["keyword_generation", "intent_classification"],
                    "cost_savings": "~50% reduction vs dual call approach"
                }
            }
            
            # Record single optimized usage
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="secondary_keywords_generation",  # Same service, optimized flow
                model_name=self.keyword_generation_usage["model_name"],
                input_tokens=self.keyword_generation_usage["input_tokens"],
                output_tokens=self.keyword_generation_usage["output_tokens"],
                service_description="Optimized secondary keywords generation with intent (single AI call)",
                project_id=project_id,
                additional_metadata=optimized_metadata
            )
            
            logger.info(f"💰 Optimized billing: ~50% cost reduction with single AI call - {result}")
            
        except Exception as e:
            logger.error(f"Failed to record optimized usage: {e}")

    def _merge_intent_with_metrics(self, keywords_with_intent: List[Dict], metrics: List[Dict]) -> Dict[str, Any]:
        """Merge AI-generated intent data with SEMrush metrics"""
        try:
            # Create intent lookup by keyword
            intent_lookup = {item["keyword"].lower(): item["intent"] for item in keywords_with_intent}
            
            # Merge with metrics
            merged_results = []
            for metric in metrics:
                keyword = metric["keyword"].lower()
                
                # Use AI intent as primary source (more accurate for intent classification)
                ai_intent = intent_lookup.get(keyword, "Informational")  # fallback
                
                merged_keyword = {
                    "keyword": metric["keyword"],
                    "search_volume": metric["search_volume"],
                    "difficulty": metric["difficulty"],
                    "intent": ai_intent  # Use AI intent instead of SEMrush intent
                }
                merged_results.append(merged_keyword)
                
                logger.info(f"🔗 Merged: '{metric['keyword']}' → Intent: {ai_intent}")
            
            # Sort by search volume descending
            merged_results.sort(key=lambda x: x["search_volume"], reverse=True)
            
            return {
                "keywords": merged_results,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error merging intent with metrics: {str(e)}")
            raise

    def manual_keywords_analysis_workflow(
        self,
        keywords: List[str],
        project_id: str,
        country: str = "in"
    ) -> Dict[str, Any]:
        """
        Manual keyword analysis workflow with billing
        
        :param keywords: List of keywords to analyze
        :param project_id: Project identifier  
        :param country: Country for localization
        :return: Processed keyword analysis results
        """
        try:
            logger.info(f"Starting manual keywords analysis workflow for {len(keywords)} keywords")
            
            # Initialize usage tracking variables
            self.intent_analysis_usage = None
            
            # Fetch metrics for provided keywords
            logger.info(f"Fetching metrics for keywords: {keywords}")
            metrics = self.fetch_metrics(keywords, country)
            logger.info(f"Raw metrics data: {metrics}")
            
            # Process initial results
            processed_results = self.process_results(metrics)
            logger.info(f"Initial processed results: {processed_results}")
            
            # Get intent analysis with tracking
            logger.info(f"Getting intent for keywords via OpenAI with tracking")
            intent_list = self.get_keyword_intent_with_tracking(keywords)
            logger.info(f"Received intent list from OpenAI: {intent_list}")
            
            # Record manual analysis usage with billing
            self._record_manual_analysis_usage(project_id, keywords, country)
            
            # Update intents for all keywords
            for i, keyword_data in enumerate(processed_results["keywords"]):
                try:
                    keyword = keyword_data["keyword"]
                    original_intent = keyword_data["intent"]
                    logger.info(f"Processing keyword '{keyword}' with original intent '{original_intent}'")
                    
                    # Use OpenAI intent if original is unknown/missing, or if index is available
                    if i < len(intent_list):
                        if original_intent.lower() in ["unknown", "-", ""]:
                            openai_intent = intent_list[i].strip().capitalize()
                            processed_results["keywords"][i]["intent"] = openai_intent
                            logger.info(f"Using OpenAI intent '{openai_intent}' for '{keyword}'")
                        else:
                            # Keep original intent but log the OpenAI result for comparison
                            openai_intent = intent_list[i].strip().capitalize()
                            processed_results["keywords"][i]["intent"] = original_intent.capitalize()
                            logger.info(f"Keeping original intent '{original_intent}' for '{keyword}' (OpenAI suggested: '{openai_intent}')")
                    else:
                        processed_results["keywords"][i]["intent"] = "Informational"
                        logger.info(f"Set fallback intent 'Informational' for '{keyword}' (index out of range)")
                        
                except Exception as e:
                    logger.error(f"Error processing intent for keyword {keyword_data['keyword']}: {e}")
                    processed_results["keywords"][i]["intent"] = "Informational"
                    logger.info(f"Set fallback intent 'Informational' for '{keyword_data['keyword']}'")
            
            logger.info(f"Manual analysis completed for {len(keywords)} keywords")
            return processed_results
            
        except Exception as e:
            logger.error(f"Manual keywords analysis workflow failed: {e}")
            raise
