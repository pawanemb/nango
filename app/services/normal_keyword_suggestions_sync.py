from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import uuid
from app.models.project import Project
from openai import OpenAI
from app.core.config import settings
from app.core.logging_config import logger
from app.tasks.keyword_suggestions import fetch_semrush_data  # Import the sync function
from sqlalchemy.orm import Session
from app.utils.token_tracking import TokenTracker
import time

class KeywordSuggestionServiceSync:
    def __init__(self, openai_api_key: Optional[str] = None, db: Optional[Session] = None, user_id: Optional[str] = None, project_id: Optional[str] = None):
        """
        Initialize KeywordSuggestionService with optional API key.
        
        :param openai_api_key: OpenAI API key. If not provided, uses settings.
        :param db: Database session for token tracking
        :param user_id: User ID for token tracking
        :param project_id: Project ID for token tracking
        """
        self.openai_client = OpenAI(
            api_key=openai_api_key or settings.OPENAI_API_KEY
        )
        self.logger = logger
        self.db = db
        self.user_id = user_id
        self.project_id = project_id

    def __del__(self):
        """Cleanup when object is deleted."""
        try:
            self.cleanup()
        except Exception as e:
            self.logger.error(f"Error during cleanup in __del__: {e}")

    def cleanup(self):
        """Cleanup OpenAI client resources."""
        if hasattr(self, 'openai_client'):
            try:
                if hasattr(self.openai_client, 'close'):
                    self.openai_client.close()
                    self.logger.info("OpenAI client closed successfully.")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
                raise RuntimeError(f"Failed to cleanup OpenAI client: {str(e)}") from e

    

    def generate_prompt(
        self,
        services: List[str],
        business_type: str,
        locations: List[str],
        target_audience: str,
        homepage_content: str,
        industry: Optional[str] = None
    ) -> str:
        """
        Generate a detailed prompt for keyword generation.
        
        :param services: List of services/products
        :param business_type: Type of business
        :param locations: List of locations
        :param target_audience: Target audience description
        :param homepage_content: Content from homepage
        :param industry: Optional industry specification
        :return: Formatted prompt string
        """
        services_str = ", ".join(services) if services else "[Add input here]"
        locations_str = ", ".join(locations) if locations else "[Add input here]"
        
        prompt = f"""Generate a list of SEO-relevant keywords from the following inputs:

Type of business: {business_type or "[Add input here]"}
List of services/products: {services_str}
Locations: {locations_str}
Target Audience: {target_audience or "[Add input here]"}
Scrapped Homepage: {homepage_content or "[Add input here]"}

Instructions:
1. For E-Commerce and SaaS businesses: 
   - Split the intent of keywords into a 4:1 ratio, favoring commercial intent over informational intent
   - Ensure 30% of the commercial intent keywords are location-based
2. For all other types of businesses:
   - Split the intent of keywords into a 1:4 ratio, favoring informational intent over commercial intent
   - Ensure 30% of the commercial intent keywords are location-based
3. The SEO relevancy of all keywords should be very high
4. Output the keywords as text separated by commas, WITHOUT any quotes
5. No grouping should be done. Output only in one line
6. No comments to be mentioned
7. Do not change the split of commercial and informational intent keywords at all
8. Do not include the name of the brand in your response
9. The name of the brand is the name of the company which is hosting these services
10. Act as a Googlebot crawler to give the list of short tail keywords have  high search volume and low difficulty keywords to rank the company with SEO efforts
11. Output not less than 10 and not more than 20 keywords
12. You are a highly experienced SEO expert who can access Ahrefs and Semrush. Make sure all keywords are short tail keywords with 2 words have high search volume and low difficulty
13. DO NOT use any quotes or special characters in the keywords
14. Dont start the response with this type of line Here are the SEO keyword suggestions directly give the keywords """

        return prompt

    def generate_keywords(
        self,
        services: List[str],
        business_type: str,
        locations: List[str],
        target_audience: str,
        homepage_content: str,
        industry: str,
        country: str = "in"
    ) -> List[str]:
        """
        Generate keyword suggestions using GPT model.
        
        :param services: List of services
        :param business_type: Type of business
        :param locations: List of locations
        :param target_audience: Target audience
        :param homepage_content: Homepage content
        :param industry: Industry type
        :param country: Country for localization
        :return: List of unique keywords
        """
        try:
            # Ensure all inputs are strings or lists of strings
            services_str = ", ".join(map(str, services))
            locations_str = ", ".join(map(str, locations))
            
            # Create the prompt
            prompt = f"""Generate SEO keyword suggestions for a {business_type} that provides {services_str}.
            Target Locations: {locations_str}
            Target Audience: {target_audience}
            Industry: {industry}
            
            Generate keywords that:
            1. Are relevant to the business services and locations
            2. Target the specific audience
            3. Include only short-tail keywords with 2-3 words
            4. DO NOT include any quotes or special characters
            5. Are in plain text format
            6. You are a highly experienced SEO expert who can access Ahrefs and Semrush. Make sure all keywords are short tail keywords with 2 words have high search volume and low difficulty
            7. Dont start the response with this type of line Here are the SEO keyword suggestions directly give the keywords
            Format each keyword on a new line without any quotes or special formatting.
            """
            
            # Get response from GPT with token tracking
            if self.db and self.user_id:
                with TokenTracker(
                    db=self.db,
                    user_id=self.user_id,
                    prompt_type="keyword_suggestions",
                    prompt_name="Primary Keyword Suggestions",
                    project_id=self.project_id,
                    model_provider="openai",
                    prompt_text=prompt,
                    extra_metadata={
                        "business_type": business_type,
                        "services": services,
                        "locations": locations,
                        "industry": industry,
                        "country": country
                    }
                ) as tracker:
                    response = self.openai_client.responses.create(
                        model=settings.OPENAI_MODEL,
                         input=[
                            {"role": "system", "content": "You are a skilled SEO expert helping to generate relevant keywords."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=settings.OPENAI_TEMPERATURE,
                        max_output_tokens=settings.OPENAI_MAX_TOKENS
                    )
                    tracker.set_response(response)
            else:
                # Fallback without tracking
                response = self.openai_client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                    {"role": "system", "content": "You are a skilled SEO expert helping to generate relevant keywords."},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Extract and clean keywords
            keywords_text = response.output_text.strip()
            keywords = [
                keyword.strip().strip('"\'').strip('.,;:').strip()
                for keyword in keywords_text.split('\n')
                if keyword.strip()
            ]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_keywords = [
                k for k in keywords 
                if not (k.lower() in seen or seen.add(k.lower()))
            ]
            
            return unique_keywords
            
        except Exception as e:
            self.logger.error(f"Failed to generate keywords: {str(e)}")
            raise RuntimeError(f"Failed to generate keywords: {str(e)}") from e

    def fetch_metrics(
        self, 
        keywords: List[str], 
        country: str = "in"
    ) -> List[Dict[str, Any]]:
        """
        Fetch metrics for keywords.
        
        :param keywords: List of keywords
        :param country: Country for localization
        :return: List of keyword metrics
        """
        try:
            # Ensure all inputs are basic Python types
            clean_keywords = list(map(str, keywords))
            
            # Fetch metrics for all keywords in one go
            metrics_results = fetch_semrush_data(clean_keywords, country)
            
            # Convert all values to basic Python types
            serializable_metrics = []
            if metrics_results:
                for metric in metrics_results:
                    serializable_metrics.append({
                        "keyword": str(metric["keyword"]),
                        "search_volume": int(metric.get("search_volume", 0)),
                        "difficulty": int(metric.get("difficulty", 0)),
                        "intent": str(metric.get("intent", "Unknown")),
                        "cpc": float(metric.get("cpc", 0.0)),
                        "competition": float(metric.get("competition", 0.0))
                    })
            else:
                for metric in clean_keywords:
                    serializable_metrics.append({
                        "keyword": metric,
                        "search_volume": 0,
                        "difficulty": 0,
                        "intent": "Unknown",
                        "cpc": 0.0,
                        "competition": 0.0
                    })
            
            return serializable_metrics
            
        except Exception as e:
            self.logger.error(f"Error fetching metrics: {e}")
            raise

    def get_related_keywords(
        self,
        keyword: str,
        country: str = "in",
        project: Project = None,
        usage_tracker: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate related keywords using OpenAI API.
        
        Args:
            keyword: The main keyword to find related keywords for
            country: Country code for localization (default: "in")
            project: Project object associated with the request (default: None)
            usage_tracker: Optional usage tracker for combined billing
            
        Returns:
            List[Dict[str, Any]]: List of related keywords with their metrics
        """
        try:
            from app.prompts.blogGenerator.related_keywords import related_keywords_prompt
            
            # Generate the prompt using the template
            prompt_data = related_keywords_prompt(
                primary_keyword=keyword,
                country=country,
                project=project,
            )
            
            # Call OpenAI API with combined usage tracking
            response = self.openai_client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                    {"role": "system", "content": prompt_data["system"]},
                    {"role": "user", "content": prompt_data["user"]}
                ],
                temperature=1,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # 🔥 COMBINED USAGE TRACKING: Accumulate tokens for related keywords generation
            if usage_tracker is not None:
                usage_tracker["total_input_tokens"] += response.usage.input_tokens
                usage_tracker["total_output_tokens"] += response.usage.output_tokens
                usage_tracker["total_calls"] += 1
                usage_tracker["individual_calls"].append({
                    "call_number": usage_tracker["total_calls"],
                    "call_type": "related_keywords_generation",
                    "primary_keyword": keyword,
                    "country": country,
                    "prompt_type": "related_keywords_pkw_suggestions",
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "model_name": response.model,
                    "temperature": 1
                })
                
                logger.info(f"📊 Related keywords generation call #{usage_tracker['total_calls']}: "
                           f"{response.usage.input_tokens} input + {response.usage.output_tokens} output tokens "
                           f"(Running total: {usage_tracker['total_input_tokens']} input, "
                           f"{usage_tracker['total_output_tokens']} output)")
            else:
                # Legacy tracking for backward compatibility
                if self.db and self.user_id:
                    with TokenTracker(
                        db=self.db,
                        user_id=self.user_id,
                        prompt_type="related_keywords_pkw_suggestions",
                        prompt_name="Related Keywords for Primary Keyword",
                        project_id=self.project_id if self.project_id else (str(project.id) if project else None),
                        model_provider="openai",
                        prompt_text=prompt_data["user"],
                        keyword_id=keyword,
                        extra_metadata={
                            "primary_keyword": keyword,
                            "country": country
                        }
                    ) as tracker:
                        # Set response for legacy tracker (no additional API call)
                        tracker.set_response(response)
            
            # Extract and process the response
            if not response.output_text:
                raise ValueError("No response from OpenAI API")
                
            # Parse the response and format keywords
            related_keywords = []
            content = response.output_text.strip()
            logger.info(f"Related keywords: {content}")
            try:
                import json
                # Parse the JSON string into a Python list
                keywords_list = json.loads(content)
                
                if not isinstance(keywords_list, list):
                    raise ValueError("Expected a list of keywords from gpt but got something different")
                
                for keyword in keywords_list:
                    keyword_data = {
                        "keyword": keyword.strip()
                    }
                    related_keywords.append(keyword_data)
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw content: {content}")
                raise ValueError("Invalid response format from OpenAI")
            
            return related_keywords
            
        except Exception as e:
            self.logger.error(f"Error in get_related_keywords: {str(e)}")
            raise

    def generate_keyword_suggestions(
        self,
        services: List[str],
        business_type: str,
        locations: List[str],
        target_audience: str,
        homepage_content: str,
        industry: str,
        country: str = "in"
    ) -> Dict[str, Any]:
        """
        Complete keyword suggestion workflow.
        
        :param services: List of services
        :param business_type: Type of business
        :param locations: List of locations
        :param target_audience: Target audience
        :param homepage_content: Homepage content
        :param industry: Industry type
        :param country: Country for localization
        :return: Processed keyword suggestions
        """
        try:
            # Generate keywords
            keywords = self.generate_keywords(
                services, business_type, locations, 
                target_audience, homepage_content, 
                industry, country
            )
            
            from app.api.v1.endpoints.keywords import get_keyword_intent
           
            # Fetch metrics
            metrics = self.fetch_metrics(keywords, country)



            intent_list_from_gpt = get_keyword_intent(keywords)
            # Create a metrics dictionary for faster lookup
            metrics_dict = {metric['keyword']: metric for metric in metrics} if metrics else {}
            
            # Process metrics for each keyword
            keywords_with_metrics = []
            for index, kw in enumerate(keywords):
                keyword = kw
                metric = metrics_dict.get(keyword, {})
                # logger.info("intent_list_from_gpt[index].capitalize(): " + intent_list_from_gpt[index].capitalize())
                keywords_with_metrics.append({
                    "name": keyword,
                    "search_volume": metric.get("search_volume", 0),
                    "keyword_difficulty": float(metric.get("difficulty", 0.0)),
                    "difficulty": float(metric.get("difficulty", 0.0)),  # Same as keyword_difficulty
                    "cpc": metric.get("cpc", 0.0),
                    "competition": metric.get("competition", 0.0),
                    # "intent": metric.get("intent", intent_list_from_gpt[index].capitalize()),
                    "intent": intent_list_from_gpt[index].capitalize(),
                    "country": country,
                    "index": index
                })
            # Process results
            # processed_results = self.process_results(metrics)
            return keywords_with_metrics
            
        except Exception as e:
            self.logger.error(f"Error generating keyword suggestions: {e}")
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
            # Clean keywords in metrics
            cleaned_metrics = []
            for metric in metrics:
                # Thorough keyword cleaning
                clean_keyword = metric["keyword"].strip().strip('"\'').strip()
                clean_keyword = clean_keyword.strip('.,;:').strip()
                clean_keyword = clean_keyword.replace('"', '').replace("'", '')
                clean_keyword = clean_keyword.rstrip('.')
                
                cleaned_metrics.append({
                    "keyword": clean_keyword,
                    "search_volume": int(metric.get("search_volume", 0)),
                    "difficulty": int(metric.get("difficulty", 0)),
                    "intent": metric.get("intent", "Unknown"),
                    "cpc": float(metric.get("cpc", 0.0)),
                    "competition": float(metric.get("competition", 0.0))
                })
            
            # Sort by search volume descending
            cleaned_metrics.sort(key=lambda x: (-x["search_volume"], x["keyword"]))
            
            return {
                "keywords": cleaned_metrics,
                "generated_at": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error processing results: {e}")
            raise

# Example usage
def main():
    service = KeywordSuggestionServiceSync()
    try:
        result = service.generate_keyword_suggestions(
            services=["web design"],
            business_type="SaaS",
            locations=["New York"],
            target_audience="Small businesses",
            homepage_content="Professional web design services",
            industry="Technology"
        )
        print(result)
    finally:
        service.cleanup()

if __name__ == "__main__":
    main()
